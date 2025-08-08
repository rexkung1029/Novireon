import discord
import logging
import time
import urllib.parse

from discord import Interaction as Itat
from discord.ext import commands
from discord.utils import get
from mongo_crud import MongoCRUD
from pymongo import MongoClient


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Music_Core")

mongo_client = MongoClient(
    "mongodb://localhost:27017/",
    serverSelectionTimeoutMS=15000
)

music_db_handler = MongoCRUD(
            client=mongo_client, 
            db_name='Norvireon_bot_db', 
            collection_name='Music_data',
            logger=logger
        )

db_handler = MongoCRUD(
    client=mongo_client, 
    db_name='Norvireon_bot_db', 
    collection_name='Music_data',
    logger=logger
)


def format_time(seconds):
    mins, secs = divmod(int(seconds), 60)
    return f"{mins}:{secs:02}"

def generate_progress_bar(guild_id):
    data = db_handler.get(query= {'_id':guild_id})[0]
    is_playing = data.get('is_playing')
    start_time = data['start_time']
    duration = data['duration']
    total_paused_duration = data['total_paused_duration']
    author = data.get('author', 'Unknown Artist')
    if duration == 0: return ""
    if total_paused_duration is None: total_paused_duration = 0

    if not is_playing:
        pause_time = data.get("pause_time", start_time)
        elapsed = int(pause_time - start_time - total_paused_duration)
    else:
        elapsed = int(time.time() - start_time - total_paused_duration)
    progress = min(elapsed / duration, 1.0)
    length = 20
    filled_length = int(length * progress)
    bar = '─' * filled_length + '•' + '─' * (length - filled_length - 1)

    if is_playing: return f"播放中\n`[{bar}]` `({format_time(elapsed)}/{format_time(duration)})`"
    else         : return f"已暫停\n`[{bar}]` `({format_time(elapsed)}/{format_time(duration)})`"

def get_source_name(url):
    """
    從 URL 中提取網站名稱。

    Args:
    url: 要從中提取網站名稱的 URL。

    Returns:
    網站名稱
    """
    hostname = urllib.parse.urlparse(url).hostname
    if hostname:
        if "youtube.com" or "youtu.be" in hostname:
            return "youtube"
    return ""

def has_role(role_id):
    """
    一個 discord.py 的檢查裝飾器，用來驗證使用者是否擁有指定的身分組。
    可以傳入身分組的名稱 (str) 或 ID (int)。
    """
    async def predicate(itat:Itat) -> bool:
        # 如果指令在私訊中使用，直接返回 False，因為私訊中沒有身分組
        if itat.guild is None:
            return False
        
        if itat.user.guild_permissions.administrator:
            return True
        
        required_role = itat.guild.get_role(role_id)

        if required_role is None or itat.user.bot:
            return False
        
        return required_role in itat.user.roles

    return commands.check(predicate)

def is_valid_url(url):
    """
    檢查給定的字串是否為有效的 URL。

    Args:
    url: 要檢查的字串。

    Returns:
    如果字串是有效的 URL，則返回 True，否則返回 False。
    """
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def return_to_default_music_settings(guild_id):
    try:
        music_db_handler.update_one(
                query={"_id":guild_id},
                new_values={
                    "current_playing":{},
                    "embed_message_id":None,
                    "is_playing":False,
                    "if_recommend": False,
                    "played":[],
                    "queue":[]
                },
                upsert=True
            )
        logger.info("returned to default music settings.")
    except Exception as e:
        logger.critical(f"Can not return to default music seettings!")
