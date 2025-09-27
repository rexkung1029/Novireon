import asyncio
import discord
import logging
import os

from discord import app_commands
from discord import Interaction as Itat
from discord import VoiceClient as VC
from discord.ext import commands
from pymongo import MongoClient

from mongo_crud import MongoCRUD
from . import music_utils
from .music_checkers import Checkers
from .music_data import voice_data
from .music_functions import Functions
from ..monster_siren import Monster_siren
from ..youtube import Youtube


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Music_Main")

ffmpeg_options = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": '-vn -filter:a "volume=0.3"',
}

mongo_uri = os.getenv("MONGO_URI")
mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=15000)

db_handler = MongoCRUD(
    client=mongo_client,
    db_name="Norvireon_bot_db",
    collection_name="Music_data",
    logger=logger,
)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Music Cog initialized with DB handler.")

    @app_commands.command(name="play", description="播放音樂")
    @app_commands.describe(request="可使用網址或直接搜尋")
    @Checkers.is_in_valid_voice_channel()
    async def command_play(self, itat: Itat, request: str):

        try:
            await itat.response.send_message("處理中", ephemeral=True)

            if itat.user.voice is None:
                await itat.followup.send(
                    "您必須先加入一個語音頻道才能使用此指令！",
                    ephemeral=True,
                    delete_after=5,
                )
                return

            guild_id = itat.guild_id

            if guild_id not in voice_data:
                voice_data[guild_id] = {}
                music_utils.return_to_default_music_settings(guild_id)

            elif "client" in voice_data[guild_id]:
                voice_client: VC = voice_data[guild_id]["client"]
                if itat.user.voice.channel.id != voice_client.channel.id:
                    await itat.followup.send(
                        "您必須先加入與機器人相同語音頻道才能使用此指令！",
                        ephemeral=True,
                        delete_after=5,
                    )
                    return

            voice_data[guild_id]["music_channel"] = itat.channel
            voice_data[guild_id]["itat"] = itat

            match music_utils.get_source_name(request):
                case "youtube":
                    data = await Youtube.get_data_from_single(request)
                case "monster_siren":
                    data = Monster_siren.get_song_data(request)
                case "":
                    data = await Functions.search(itat, request)
                    if data is None:
                        return

            if data is None:
                await itat.followup.send(
                    "找不到相關的音樂，請嘗試其他關鍵字或網址", ephemeral=True
                )
                return
            else:
                db_handler.append(query={"_id": guild_id}, field="queue", value=data)

            title = data.get("title", "Unknown Title")
            thumbnail = data.get("thumbnail", "")
            duration = data.get("duration", 0)
            author = data.get("author", "Unknown Artist")

            if ("client" not in voice_data[guild_id]) or (
                not voice_data[guild_id]["client"].is_connected()
            ):
                await itat.followup.send("正在處理播放請求", ephemeral=True)
                await Functions._play(guild_id)

            else:
                embed = discord.Embed(
                    color=0x28FF28,
                    title=f"加入佇列:\n{title}",
                    description=f"by {author}",
                )
                embed.add_field(name="時長", value=music_utils.format_time(duration))
                user = itat.user.nick if itat.user.nick else itat.user.name
                embed.add_field(name="\u200b", value=f"由{user}加入")
                embed.set_thumbnail(url=thumbnail)
                await itat.channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Command_play Error {e}")
            await itat.followup.send("執行指令時發生錯誤，請稍後再試。", ephemeral=True)

    @app_commands.command(name="play_playlist", description="播放播放列表")
    @Checkers.is_in_valid_voice_channel()
    @app_commands.describe(
        request="僅可使用youtube網址", max_results="最多加入幾首歌，預設5，最多25"
    )
    async def command_play_playlist(
        self, itat: Itat, request: str, max_results: int = 5
    ):
        try:
            await itat.response.send_message("處理中", ephemeral=True)

            if itat.user.voice is None:
                await itat.followup.send(
                    "您必須先加入一個語音頻道才能使用此指令！",
                    ephemeral=True,
                    delete_after=5,
                )
                return

            guild_id = itat.guild_id

            if guild_id not in voice_data:
                voice_data[guild_id] = {}
                music_utils.return_to_default_music_settings(guild_id)

            elif "client" in voice_data[guild_id]:
                voice_client: VC = voice_data[guild_id]["client"]
                if itat.user.voice.channel.id != voice_client.channel.id:
                    await itat.followup.send(
                        "您必須先加入與機器人相同語音頻道才能使用此指令！",
                        ephemeral=True,
                        delete_after=5,
                    )
                    return

            voice_data[guild_id]["music_channel"] = itat.channel
            voice_data[guild_id]["itat"] = itat

            datas = await Youtube.get_data_from_list(request, max_results)
            if datas is None:
                await itat.followup.send(
                    "找不到相關的播放列表，請嘗試其他關鍵字或網址", ephemeral=True
                )
                return
            else:
                user = itat.user.nick if itat.user.nick else itat.user.name
                for data in datas:
                    db_handler.append(
                        query={"_id": guild_id}, field="queue", value=data
                    )
                    title = data.get("title", "Unknown Title")
                    thumbnail = data.get("thumbnail", "")
                    duration = data.get("duration", 0)
                    author = data.get("author", "Unknown Artist")

                    embed = discord.Embed(
                        color=0x28FF28,
                        title=f"加入佇列:\n{title}",
                        description=f"by {author}",
                    )
                    embed.add_field(
                        name="時長", value=music_utils.format_time(duration)
                    )
                    embed.add_field(name="\u200b", value=f"由{user}加入")
                    embed.set_thumbnail(url=thumbnail)
                    await itat.channel.send(embed=embed)
                    await asyncio.sleep(1)

            if ("client" not in voice_data[guild_id]) or (
                not voice_data[guild_id]["client"].is_connected()
            ):
                await itat.followup.send("正在處理播放請求", ephemeral=True)
                await Functions._play(guild_id)

        except Exception as e:
            logger.error(f"Command_play_playlist Error {e}")
            await itat.followup.send("執行指令時發生錯誤，請稍後再試。", ephemeral=True)

    @app_commands.command(name="stop", description="停止播放音樂")
    @Checkers.is_dj()
    @Checkers.is_in_valid_voice_channel()
    async def command_stop(self, itat: Itat):
        await itat.response.send_message("處理中", ephemeral=True, delete_after=5)
        guild_id = itat.guild_id
        await Functions._stop(guild_id)

    @app_commands.command(name="skip", description="跳過當前曲目")
    @Checkers.is_dj()
    @Checkers.is_in_valid_voice_channel()
    async def command_skip(self, itat: Itat):
        await itat.response.send_message("處理中", ephemeral=True, delete_after=5)
        guild_id = itat.guild_id
        await Functions._skip(guild_id)

    @app_commands.command(name="pause", description="暫停音樂")
    @Checkers.is_dj()
    @Checkers.is_in_valid_voice_channel()
    async def command_pause(self, itat: Itat):
        await itat.response.send_message("處理中", ephemeral=True, delete_after=5)
        guild_id = itat.guild_id
        await Functions._pause(guild_id)

    @app_commands.command(name="resume", description="繼續播放")
    @Checkers.is_dj()
    @Checkers.is_in_valid_voice_channel()
    async def command_resume(self, itat: Itat):
        await itat.response.send_message("處理中", ephemeral=True, delete_after=5)
        guild_id = itat.guild_id
        await Functions._resume(guild_id)
