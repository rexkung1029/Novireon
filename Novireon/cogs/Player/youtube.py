import asyncio
import logging
import yt_dlp

from Novireon.src.util.config import get_config

logger = logging.getLogger("player.youtube")
logger.setLevel(logging.INFO)
player_config = get_config("Player")
youtube_base_url = "https://www.youtube.com/"
youtube_watch_url = youtube_base_url + "watch?v="


class Youtube:
    @staticmethod
    async def get_playlist_metadata(url: str):
        """
        從 YouTube URL 提取影片或播放列表的所有影片連結，不進行下載。
        """
        yt_dl_options = {
            "format": "bestaudio/best",
            "extract_flat": True,
            "noplaylist": False,
            "force_noplaylist": False,
            "source_address": "0.0.0.0",
            "playlistend": 50,
            "cookiefile": "youtube_cookies.txt",
        }

        try:

            def fetch_info():
                with yt_dlp.YoutubeDL(yt_dl_options) as ydl:
                    return ydl.extract_info(url, download=False)

            logger.info(f"正在提取 URL 的影片連結: {url}")
            raw_data = await asyncio.to_thread(fetch_info)
            if not raw_data:
                return []

            entries = []
            if raw_data.get("_type") == "playlist":
                entries = raw_data.get("entries", [])
                logger.info(f"檢測到播放列表，共有 {len(entries)} 個條目。")
            else:
                entries = [raw_data]

            playlist_metadata = []
            for entry in entries:
                if entry is None:
                    continue
                playlist_metadata.append(
                    {
                        "webpage_url": entry.get("webpage_url") or entry.get("url"),
                    }
                )
            return playlist_metadata

        except Exception as e:
            logger.error(f"提取影片連結時發生錯誤: {e}")
            return None

    @staticmethod
    async def get_data_from_single(request) -> dict:
        yt_dl_options = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "forcenoplaylist": True,
            "ignoreerrors": True,
        }

        def fetch_info():
            with yt_dlp.YoutubeDL(yt_dl_options) as ydl:
                return ydl.extract_info(request, download=False)

        raw_data = await asyncio.to_thread(fetch_info)
        # if "DVR" in raw_data.get("url"):
        #     raise ValueError("不可回放直播影片不支援播放")
        data = {
            "author": raw_data.get("uploader", "Unknown Artist"),
            "duration": raw_data.get("duration", None),
            "song_url": raw_data["url"],
            "title": raw_data["title"],
            "thumbnail": raw_data.get("thumbnail", ""),
            "is_live": raw_data.get("is_live", False),
        }
        return data

    @staticmethod
    async def get_youtube_search_results(
        search_query: str, max_results: int = player_config["limits.max_yt_search_results"]
    ) -> dict:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
        }

        query = f"ytsearch{max_results}:{search_query}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)

            results = []
            if "entries" in info:
                for entry in info["entries"]:
                    if entry["live_status"] == "is_live" or entry["duration"] is None:
                        continue
                    results.append(
                        {
                            "title": entry["title"],
                            "url": entry["url"],
                            "author": entry.get("uploader", "Unknown Artist"),
                            "duration": entry.get("duration", None),
                        }
                    )
            return results
