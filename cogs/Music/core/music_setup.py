import discord
import logging
import os

from discord     import app_commands
from discord.ext import commands
from pymongo     import MongoClient
from mongo_crud  import MongoCRUD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Music_Setup")

mongo_uri = os.getenv("MONGO_URI")
mongo_client = MongoClient(
    mongo_uri,
    serverSelectionTimeoutMS=15000
)

db_handler = MongoCRUD(
    client=mongo_client, 
    db_name='Norvireon_bot_db', 
    collection_name='Music_data',
    logger=logger
)

class MusicSetup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    music_setup = app_commands.Group(
        name="music_setup",
        description="Music setting up commands.",
        guild_only=True
    )

    @music_setup.command(name="channel", description="設定哪個語音頻道可以使用音樂指令。")
    @app_commands.describe(channel="用於發送指令的文字頻道ID，留白則允許所有頻道。")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_music_channel(self, itat: discord.Interaction, channel: discord.TextChannel = None):
        if channel:
            db_handler.update_one(
                query={},
                new_values={"music_channel_id": channel.id},
                upsert=True
            )
            await itat.response.send_message(f"已設定{channel.mention}作為音樂指令頻道。", ephemeral=True)
        else:
            # If no channel is provided, remove the restriction
            db_handler.update_one(
                query={},
                new_values={"music_channel_id": None},
                upsert=True
            )
            await itat.response.send_message("音樂指令已在所有頻道允許", ephemeral=True)

    @music_setup.command(name="dj_role", description="使定可控制音樂播放的身分組")
    @app_commands.describe(role="被指定為'DJ'的身分組。留白則僅管理員可控制。")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_dj_role(self, itat: discord.Interaction, role: discord.Role = None):
        if role:
            db_handler.update_one(
                query={},
                new_values={"dj_role_id": role.id},
                upsert=True
            )
            await itat.response.send_message(f"`{role.name}` 已被設為'DJ'的身分組。", ephemeral=True)
        else:
            # If no role is provided, remove the DJ role
            db_handler.update_one(
                query={},
                new_values={"dj_role_id": None},
                upsert=True
            )
            await itat.response.send_message("DJ身分組已被移除，僅管理員可控制音樂播放。", ephemeral=True)

    @set_music_channel.error
    @set_dj_role.error
    async def on_music_setup_error(self, itat: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await itat.response.send_message("You need the 'Manage Server' permission to use this command.", ephemeral=True)
        else:
            await itat.response.send_message(f"An unexpected error occurred: {error}", ephemeral=True)
            raise error
        
async def setup(bot: commands.Bot):
    await bot.add_cog(MusicSetup(bot))
