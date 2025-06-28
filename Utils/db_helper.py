# your_bot_project/Utils/db_helper.py
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import logging

_log = logging.getLogger(__name__)

load_dotenv()
MONGO_URI = os.getenv('MONGO_URI')

client: AsyncIOMotorClient = None
db = None # 確保初始化為 None

async def connect_to_mongo():
    """連接到 MongoDB 並獲取資料庫實例。"""
    global client, db
    if not MONGO_URI:
        _log.error("MONGO_URI not found in .env file. MongoDB connection failed.")
        return None

    try:
        client = AsyncIOMotorClient(MONGO_URI)
        db = client.get_database('Novireon_Bot_DB') 
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

def get_db():
    """返回 MongoDB 資料庫實例。"""
    return db

def get_collection(collection_name: str):
    """獲取指定名稱的集合。"""
    # 這裡就是需要修改的地方
    if db is not None: # 將 if db: 改為 if db is not None:
        return db[collection_name]
    else:
        _log.error("MongoDB is not connected. Cannot get collection.")
        return None