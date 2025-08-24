import asyncio
import logging
import re
import os
import yt_dlp

from googleapiclient.discovery import build

YOUTUBE_API_KEY = os.getenv("GOOGLE")

youtube_base_url = 'https://www.youtube.com/'
youtube_watch_url = youtube_base_url + 'watch?v='
yt_dl_options = {"format": "bestaudio/best"}
ytdl = yt_dlp.YoutubeDL(yt_dl_options)
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Youtube")

class Youtube:
    async def get_data(request):
        vid = Youtube.get_youtube_video_id(request)
        url = youtube_watch_url + vid
        raw_data = await asyncio.to_thread(ytdl.extract_info, url=url, download=False)
        data={
            "author":raw_data.get('uploader', 'Unknown Artist'),
            "duration" : raw_data['duration'],
            "song_url" : raw_data['url'],
            "title" : raw_data['title'],
            "thumbnail" : raw_data.get('thumbnail', '')
        }
        return data

    def get_youtube_video_id(url: str) -> str | None:
        if not isinstance(url, str):
            return None
            
        # 正規表示式，匹配各種 YouTube 網址格式
        # 解說請見下方
        regex_pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|embed\/|v\/|shorts\/|live\/)?([a-zA-Z0-9_-]{11})'
        
        match = re.search(regex_pattern, url)
        
        if match:
            return match.group(1)
        
        return None

    @staticmethod
    async def get_youtube_search_results(search_query: str, max_results: int = 10):
        try:
            loop = asyncio.get_event_loop()
            request = youtube.search().list(
                q=search_query,
                part="snippet",
                maxResults=max_results,
                type="video",
                relevanceLanguage="zh-TW",
                regionCode="TW"
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

