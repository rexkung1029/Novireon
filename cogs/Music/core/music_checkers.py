import logging
import os

from discord import app_commands
from discord import Interaction as Itat
from discord import VoiceClient as VC
from pymongo import MongoClient

from .music_data import voice_data
from mongo_crud  import MongoCRUD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Music_Core")


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

class Checkers():
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
                return dj_role_id in [role.id for role in itat.user.roles]
            
            return False
        return app_commands.check(predicate)
