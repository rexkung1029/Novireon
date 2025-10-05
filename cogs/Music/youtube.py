import asyncio
import logging
import random
import os
import yt_dlp

from googleapiclient.discovery import build

YOUTUBE_API_KEY = os.getenv("GOOGLE")

youtube_base_url = "https://www.youtube.com/"
youtube_watch_url = youtube_base_url + "watch?v="
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Youtube")


class Youtube:
    @staticmethod
    async def get_playlist_metadata(url: str):
        """
        從 YouTube URL 提取影片或播放列表的所有元數據，不進行下載。
        """
        yt_dl_options = {
            "format": "bestaudio/best",
            "extract_flat": True,
            "noplaylist": False,
            "force_noplaylist": False,
            "source_address": "0.0.0.0",
            "playlistend": 50,
        }

        ytdl = yt_dlp.YoutubeDL(yt_dl_options)

        try:
            logger.info(f"正在提取 URL 的元數據: {url}")
            raw_data = await asyncio.to_thread(
                ytdl.extract_info,
                url=url,
                download=False,
            )

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
            logger.error(f"提取元數據時發生錯誤: {e}")
            return None

    @staticmethod
    async def get_data_from_list(request: str, max_results: int) -> list[dict] | None:
        playlist_metadata = await Youtube.get_playlist_metadata(request)

        if not playlist_metadata:
            logger.error("未能獲取播放列表元數據，無法進行下載。")
            return
        selected_songs = random.sample(
            playlist_metadata,
            min(max_results, len(playlist_metadata), 25),  # 確保不超過總數或 25
        )
        video_info = []
        for song in selected_songs:
            info = await Youtube.get_data_from_single(song["webpage_url"])
            if info:
                video_info.append(info)
        return video_info

    @staticmethod
    async def get_data_from_single(request) -> dict:
        yt_dl_options = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "forcenoplaylist": True,
            "ignoreerrors": True,
        }
        ytdl = yt_dlp.YoutubeDL(yt_dl_options)
        raw_data = await asyncio.to_thread(
            ytdl.extract_info, url=request, download=False
        )
        data = {
            "author": raw_data.get("uploader", "Unknown Artist"),
            "duration": raw_data["duration"],
            "song_url": raw_data["url"],
            "title": raw_data["title"],
            "thumbnail": raw_data.get("thumbnail", ""),
        }
        return data

    @staticmethod
    async def get_youtube_search_results(
        search_query: str, max_results: int = 10
    ) -> dict:
        try:
            loop = asyncio.get_event_loop()
            request = youtube.search().list(
                q=search_query,
                part="snippet",
                maxResults=max_results,
                type="video",
                relevanceLanguage="zh-TW",
                regionCode="TW",
            )
            response = await loop.run_in_executor(None, request.execute)

            results = []
            for item in response.get("items", []):
                video_id = item["id"]["videoId"]
                title = item["snippet"]["title"]
                author = item["snippet"]["channelTitle"]
                song_url = youtube_watch_url + video_id
                results.append([song_url, title, author])
            return results
        except Exception as e:
            logger.error(f"get_youtube_search_results error: {e}")
            return []
