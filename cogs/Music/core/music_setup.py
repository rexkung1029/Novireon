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

    @music_setup.command(name="channel", description="Set the channel where music commands can be used.")
    @app_commands.describe(channel="The text channel to allow music commands in. Leave blank to allow all channels.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_music_channel(self, itat: discord.Interaction, channel: discord.TextChannel = None):
        """Sets the designated music command channel."""
        guild_id = itat.guild_id
        
        if channel:
            db_handler.update_one(
                query={},
                new_values={"music_channel_id": channel.id},
                upsert=True
                )
            await itat.response.send_message(f"Music commands are now restricted to {channel.mention}.", ephemeral=True)
        else:
            # If no channel is provided, remove the restriction
            db_handler.update_one(
                query={},
                new_values={"music_channel_id": None},
                upsert=True
                )
            await itat.response.send_message("Music commands can now be used in any channel.", ephemeral=True)

    @music_setup.command(name="dj_role", description="Set the role that is allowed to control the music player.")
    @app_commands.describe(role="The role to be designated as 'DJ'. Leave blank to remove the DJ role.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_dj_role(self, itat: discord.Interaction, role: discord.Role = None):
        """Sets or removes the DJ role."""
        guild_id = itat.guild_id
        
        if role:
            db_handler.update_one(
                query={},
                new_values={"dj_role_id": role.id},
                upsert=True
                )
            await itat.response.send_message(f"The `{role.name}` role is now the DJ role.", ephemeral=True)
        else:
            # If no role is provided, remove the DJ role
            db_handler.update_one(
                query={},
                new_values={"dj_role_id": None},
                upsert=True
                )
            await itat.response.send_message("DJ role has been removed. Only Admins can control the bot now.", ephemeral=True)

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
