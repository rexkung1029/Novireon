import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging

from Utils import db_helper 

_log = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv('DISCORD')
DEFAULT_PREFIX = os.getenv('DEFAULT_PREFIX', '!')

logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True # 需要啟用 members intent 才能正確獲取 channel.members 列表

bot = commands.Bot(command_prefix=DEFAULT_PREFIX, intents=intents)

async def load_all_cogs(bot_instance):
    # 載入 cogs 資料夾下的所有模組
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

    # 載入 core/Watcher 模組
    # 需要明確指定路徑，因為它不在 cogs 資料夾下
    watcher_module_path = 'core.Watcher.voice_channel_status' 
    try:
        await bot_instance.load_extension(watcher_module_path)
        _log.info(f'Loaded Watcher Module: {watcher_module_path}')
    except Exception as e:
        _log.error(f'Failed to load Watcher Module {watcher_module_path}: {e}', exc_info=True)


@bot.event
async def on_ready():
    _log.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    _log.info('------')
    
    await db_helper.connect_to_mongo() 

    await load_all_cogs(bot)
    _log.info('All modules loading process completed.')

@bot.event
async def on_disconnect():
    _log.info("Bot disconnected.")
    await db_helper.close_mongo_connection()

@bot.event
async def on_connect():
    _log.info("Bot reconnected.")
    if db_helper.db is None:
        await db_helper.connect_to_mongo()


if TOKEN:
    bot.run(TOKEN)
else:
    _log.error("Error: DISCORD_BOT_TOKEN not found in .env file.")