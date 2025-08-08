import asyncio
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
from logging_config import setup_logging
from mongo_crud import MongoCRUD
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure



_log = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv('DISCORD')
DEFAULT_PREFIX = os.getenv('DEFAULT_PREFIX', '!')

intents = discord.Intents.all()

bot = commands.Bot(command_prefix=DEFAULT_PREFIX, intents=intents)

async def load_all_cogs(bot_instance):
    cogs_base_dir = 'cogs'
    for item_name in os.listdir(cogs_base_dir):
        item_path = os.path.join(cogs_base_dir, item_name)
        if os.path.isdir(item_path) and '__init__.py' in os.listdir(item_path):
            module_path = f"{cogs_base_dir}.{item_name}" 
            try:
                await bot_instance.load_extension(module_path)
                _log.info(f'Loaded Cog Package: {module_path}')
            except Exception as e:
                _log.error(f'Failed to load Cog Package {module_path}: {e}', exc_info=True)



@bot.event
async def on_ready():
    setup_logging()
    await load_all_cogs(bot)
    _log.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    _log.info("syncing...")
    await bot.tree.sync()
    _log.info(">>Bot is online<<")


@bot.event
async def on_disconnect():
    _log.info("Bot disconnected.")


if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
