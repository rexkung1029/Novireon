import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
import Util

# 載入環境變數
load_dotenv()
TOKEN = os.getenv('DISCORD')
YOUTUBE_API_KEY= os.getenv('GOOGLE')


# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
_log = logging.getLogger(__name__)

# 定義 Bot 的 Intents
intents = discord.Intents.all()

# 初始化 Bot
bot = commands.Bot(command_prefix = ("!","0","?"),intents=intents)

async def load_cogs(bot):
    cogs_base_dir = 'cogs'
    
    # 我們遍歷 cogs 目錄下的直接子資料夾 (或直接的 .py 檔案)
    # 這裡假設每個直接子資料夾都代表一個聚合 Cog，並且其 __init__.py 包含 setup 函數
    # 或者直接的 .py 檔案也是一個 Cog
    
    for item_name in os.listdir(cogs_base_dir):
        item_path = os.path.join(cogs_base_dir, item_name)
        module_path = None

        if os.path.isdir(item_path):
            # 如果是資料夾，且內部有 __init__.py，則視為一個包 Cog
            if '__init__.py' in os.listdir(item_path):
                module_path = f"{cogs_base_dir}.{item_name}" # 例如: cogs.func
        elif os.path.isfile(item_path) and item_name.endswith('.py') and not item_name.startswith('__'):
            # 如果是 .py 檔案，直接載入
            module_path = f"{cogs_base_dir}.{item_name[:-3]}" # 例如: cogs.general

        if module_path:
            try:
                await bot.load_extension(module_path)
                _log.info(f'Loaded Cog/Package: {module_path}')
            except Exception as e:
                _log.error(f'Failed to load Cog/Package {module_path}: {e}', exc_info=True)



@bot.event
async def on_ready():
    _log.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    _log.info('---------------------------------------------')
    await load_cogs(bot)
    _log.info('All cogs loading process completed.')
    await Util.db_helper.connect_to_mongo()
    _log.info("Syncing...")
    await bot.tree.sync()
    _log.info("Synced!")

@bot.event
async def on_disconnect():
    _log.info("Bot disconnected.")
    # 在 Bot 斷開連接時關閉 MongoDB 連接
    await Util.db_helper.close_mongo_connection()

@bot.event
async def on_connect():
    _log.info("Bot reconnected.")
    # 如果斷線重連，確保 MongoDB 連接仍然存在或重新連接
    if not Util.db_helper.db:
        await Util.db_helper.connect_to_mongo()

# 執行 Bot
if TOKEN:
    bot.run(TOKEN)
else:
    _log.error("Error: DISCORD_BOT_TOKEN not found in .env file.")