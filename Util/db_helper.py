import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient # 異步 MongoDB 驅動
import logging

_log = logging.getLogger(__name__)

# 載入環境變數
load_dotenv()
MONGO_URI = os.getenv('MONGO_URI')


# 推薦使用異步驅動 motor，因為 discord.py 是異步的
client: AsyncIOMotorClient = None
db = None
async def connect_to_mongo():
    """連接到 MongoDB 並獲取資料庫實例。"""
    global client, db
    if not MONGO_URI:
        _log.error("MONGO_URI not found in .env file. MongoDB connection failed.")
        return None

    try:
        client = AsyncIOMotorClient(MONGO_URI)
        # 這裡 'your_bot_db' 是你的資料庫名稱
        db = client.get_database('your_bot_db') 
        
        # 嘗試列出集合，以測試連接是否成功
        await db.list_collection_names() 
        _log.info("Successfully connected to MongoDB!")
        return db
    except Exception as e:
        _log.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
        return None

async def close_mongo_connection():
    """關閉 MongoDB 連接。"""
    global client
    if client:
        client.close()
        _log.info("MongoDB connection closed.")

def get_collection(collection_name: str):
    """獲取指定名稱的集合。"""
    if db:
        return db[collection_name]
    else:
        _log.error("MongoDB is not connected. Cannot get collection.")
        return None