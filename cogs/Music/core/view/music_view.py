import discord
import logging
import os

from discord import ButtonStyle
from discord.ui import Button
from pymongo import MongoClient

from mongo_crud import MongoCRUD
from ..music_checkers import Checkers
from ..music_functions import Functions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Music_Core")

mongo_uri = os.getenv("MONGO_URI")
mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=15000)

db_handler = MongoCRUD(
    client=mongo_client,
    db_name="Norvireon_bot_db",
    collection_name="Music_data",
    logger=logger,
)


class Views:
    # A button that toggles between Pause and Resume
    class PauseResumeButton(discord.ui.Button):
        def __init__(self, guild_id: int):
            self.data = db_handler.get(query={"_id": guild_id})[0]
            self.is_paused = not (self.data.get("is_playing"))
            # Set style and label based on the current state
            style = ButtonStyle.green if self.is_paused else ButtonStyle.primary
            label = "繼續" if self.is_paused else "暫停"
            emoji = "▶️" if self.is_paused else "⏸️"

            super().__init__(style=style, label=label, emoji=emoji)
            self.guild_id = guild_id

        async def callback(self, itat: discord.Interaction):
            if not Checkers._is_dj(itat) or not Checkers._is_in_valid_voice_channel(
                itat
            ):
                await itat.response.send_message(
                    "你沒有足夠的權限", ephemeral=True, delete_after=5
                )
                return
            await itat.response.send_message(
                "正在處理請求", ephemeral=True, delete_after=5
            )
            if self.is_paused:
                await Functions._resume(self.guild_id)
            else:
                await Functions._pause(self.guild_id)

    # Button to skip to the next song
    class SkipButton(discord.ui.Button):
        def __init__(self, guild_id: int):
            super().__init__(style=ButtonStyle.secondary, label="下一首", emoji="⏭️")
            self.guild_id = guild_id

        async def callback(self, itat: discord.Interaction):
            if not Checkers._is_dj(itat) or not Checkers._is_in_valid_voice_channel(
                itat
            ):
                await itat.response.send_message(
                    "你沒有足夠的權限", ephemeral=True, delete_after=5
                )
                return
            await itat.response.send_message(
                "正在處理請求", ephemeral=True, delete_after=5
            )
            await Functions._skip(self.guild_id)

    # Button to stop playback and disconnect
    class StopButton(discord.ui.Button):
        def __init__(self, guild_id: int):
            super().__init__(style=ButtonStyle.danger, label="停止", emoji="⏹️")
            self.guild_id = guild_id

        async def callback(self, itat: discord.Interaction):
            if not Checkers._is_dj(itat) or not Checkers._is_in_valid_voice_channel(
                itat
            ):
                await itat.response.send_message(
                    "你沒有足夠的權限", ephemeral=True, delete_after=5
                )
                return
            await itat.response.send_message(
                "正在處理請求", ephemeral=True, delete_after=5
            )
            # We call the main _stop functions which handles everything
            await Functions._stop(self.guild_id)

    class Regret(Button):
        def __init__(self, guild_id):
            self.guild_id = guild_id
            super().__init__(label="移出佇列", style=ButtonStyle.red)

        async def callback(self, itat: discord.Interaction):
            await itat.response.send_message(
                "本功能暫時不可用", ephemeral=True, delete_after=5
            )
            # await Functions.remove_from_queue(self.guild_id, -1)
