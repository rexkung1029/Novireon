import discord 
import logging
import time
import asyncio

from discord.ext import commands
from discord.ui import View
from discord import app_commands
from discord import Interaction as Itat
from discord import VoiceClient as VC
from pymongo import MongoClient

from ..youtube import Youtube
from .music_data import voice_data
from mongo_crud import MongoCRUD
from .music_functions import Functions
from . import music_utils


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Music_Core")

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=0.3"'
}

mongo_uri = "mongodb://localhost:27017/"
mongo_client = MongoClient(
    "mongodb://localhost:27017/",
    serverSelectionTimeoutMS=15000
)

db_handler = MongoCRUD(
    client=mongo_client, 
    db_name='Norvireon_bot_db', 
    collection_name='Music_data',
    logger=logger
)

class Checks():
    @staticmethod
    def is_in_valid_voice_channel():
        """檢查使用者是否與機器人在同一個語音頻道。"""
        def predicate(itat:Itat) -> bool:
            guild_id = itat.guild_id
            if guild_id not in voice_data: return True
            client:VC = voice_data[guild_id]["client"]
            if itat.guild.voice_client is None:
                return True
            if itat.user.voice is None:
                return False
            return itat.user.voice.channel.id == client.channel.id
        return app_commands.check(predicate)
    
    @staticmethod
    def is_dj():
        def predicate(itat:Itat) -> bool:
            guild_id = itat.guild_id
            settings = db_handler.get(query={"_id":guild_id})[0]
            dj_role_id = settings.get('dj_role_id', None)

            if itat.user.guild_permissions.administrator :return True
            
            elif dj_role_id is not None:
                if_dj = False
                for role in itat.user.roles :
                    if role.id == dj_role_id : if_dj = True
                return if_dj
            
            elif dj_role_id is None :return False
        return app_commands.check(predicate)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Music Cog initialized with DB handler.")
 
    @app_commands.command(name="play", description="播放音樂")
    @app_commands.describe(request="可使用網址或直接搜尋")
    @Checks.is_in_valid_voice_channel()
    async def command_play(self, itat:Itat, request:str):
        try:
            await itat.response.send_message("處理中", ephemeral=True)

            if itat.user.voice is None:
                await itat.followup.send("❌ 您必須先加入一個語音頻道才能使用此指令！",ephemeral=True, delete_after=5)
                return

            guild_id = itat.guild_id

            if guild_id not in voice_data:
                voice_data[guild_id] = {}
                music_utils.return_to_default_music_settings(guild_id)
            else:
                voice_client:VC = voice_data[guild_id]["client"]
                if itat.user.voice.channel.id != voice_client.channel.id:
                    await itat.followup.send("❌ 您必須先加入與機器人相同語音頻道才能使用此指令！",ephemeral=True, delete_after=5)
                    return

            voice_data[guild_id]["music_channel"]=itat.channel
            voice_data[guild_id]["itat"]=itat

            match music_utils.get_source_name(request):
                case "youtube":
                    data = await Youtube.get_data(request)
                    db_handler.append(
                        query={"_id":guild_id},
                        field="queue",
                        value=data
                    )
                case '' :
                    await Functions.search(itat, request)
                    return
                

            title = data.get('title', 'Unknown Title')
            thumbnail = data.get('thumbnail', '')
            duration = data['duration']
            author = data.get('author', 'Unknown Artist')

            if "client" not in voice_data[guild_id] or not voice_data[guild_id]["client"].is_connected():
                await itat.followup.send("正在處理播放請求", ephemeral=True)
                await Functions._play(guild_id)
                    
            else:
                embed = discord.Embed(color=0x28ff28, title=f"加入佇列: {title}", description=f"by {author}")
                embed.set_thumbnail(url=thumbnail)
                embed.add_field(name="時長", value=music_utils.format_time(duration))
                await itat.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Command_play Error {e}")

    @app_commands.command(name="stop", description="停止播放音樂")
    @Checks.is_dj()
    @Checks.is_in_valid_voice_channel()
    async def command_stop(self, itat:Itat):
        await itat.response.send_message("處理中", ephemeral=True, delete_after=5)
        guild_id = itat.guild_id
        await Functions._stop(guild_id)

    @app_commands.command(name="skip", description="跳過當前曲目")
    @Checks.is_dj()
    @Checks.is_in_valid_voice_channel()
    async def command_skip(self, itat:Itat):
        await itat.response.send_message("處理中", ephemeral=True, delete_after=5)
        guild_id = itat.guild_id
        await Functions._skip(guild_id)

    @app_commands.command(name="pause", description="暫停音樂")
    @Checks.is_dj()
    @Checks.is_in_valid_voice_channel()
    async def command_pause(self, itat:Itat):
        await itat.response.send_message("處理中", ephemeral=True, delete_after=5)
        guild_id = itat.guild_id
        await Functions._pause(guild_id)    

    @app_commands.command(name="resume", description="繼續播放")
    @Checks.is_dj()
    @Checks.is_in_valid_voice_channel()
    async def command_resume(self, itat:Itat):
        await itat.response.send_message("處理中", ephemeral=True, delete_after=5)
        guild_id = itat.guild_id
        await Functions._resume(guild_id)  

    