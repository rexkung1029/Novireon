# your_bot_project/cogs/TempVC/temp_vc_commands.py
import discord
from discord.ext import commands, tasks
import logging
import asyncio
import datetime # 用於儲存時間戳

from Utils import db_helper 

_log = logging.getLogger(__name__)

class TempVCCommands(commands.Cog):
    """
    提供自動創建和管理臨時語音頻道的核心功能。
    """

    def __init__(self, bot):
        self.bot = bot
        # 用於追蹤臨時語音頻道狀態 {頻道ID: delete_timestamp (或 None)}
        self.temp_channels_to_monitor = {} 
        self.DELETE_DELAY_SECONDS = 30 
        
        # 獲取用於儲存伺服器配置的集合 (用於獲取創建頻道ID)
        self.guild_config_collection = db_helper.get_collection('guild_configs')
        if self.guild_config_collection is None:
            _log.error("Failed to get 'guild_configs' collection for TempVCCommands. DB might not be connected.")

        # 獲取用於儲存臨時頻道ID的集合 (新的集合)
        self.temp_channels_db_collection = db_helper.get_collection('temp_channels')
        if self.temp_channels_db_collection is None:
            _log.error("Failed to get 'temp_channels' collection for TempVCCommands. DB might not be connected.")

        self.check_empty_temp_channels.start()
        _log.info("TempVCCommands Cog initialized and background task started.")

    def cog_unload(self):
        self.check_empty_temp_channels.cancel()
        _log.info("TempVCCommands Cog unloaded and background task cancelled.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        if self.guild_config_collection is None or self.temp_channels_db_collection is None:
            _log.warning(f"on_voice_state_update: DB collections not available for {member.guild.name}.")
            return

        guild_id = member.guild.id
        config_doc = await self.guild_config_collection.find_one({'_id': guild_id})
        
        creation_channel_id = None
        if config_doc:
            creation_channel_id = config_doc.get('temp_vc_creation_channel_id')

        # --- 處理創建臨時頻道 ---
        if after.channel and after.channel.id == creation_channel_id:
            _log.info(f"{member.display_name} 加入了創建頻道 (ID: {creation_channel_id})。")
            if before.channel != after.channel:
                await self._create_and_move_to_temp_channel(member, after.channel)
                return

        # --- 處理刪除臨時頻道 ---
        # 檢查用戶是否離開了任何語音頻道
        if before.channel:
            # 檢查這個頻道是否被我們的 Bot 創建並記錄在資料庫中
            is_temp_channel_in_db = await self.temp_channels_db_collection.find_one({'_id': before.channel.id})
            
            if is_temp_channel_in_db:
                _log.info(f"{member.display_name} 離開了臨時頻道 '{before.channel.name}' (由資料庫識別)。")
                
                # 確保頻道確實是空的
                if not before.channel.members: 
                    # 設置刪除計時，如果它還不在監控列表
                    if before.channel.id not in self.temp_channels_to_monitor or \
                       self.temp_channels_to_monitor[before.channel.id] is None:
                        self.temp_channels_to_monitor[before.channel.id] = asyncio.get_event_loop().time() + self.DELETE_DELAY_SECONDS
                        _log.info(f"臨時頻道 '{before.channel.name}' (ID: {before.channel.id}) 變空，將在 {self.DELETE_DELAY_SECONDS} 秒後檢查刪除。")
                else:
                    # 如果頻道不空，則從監控列表移除（如果存在），或者不設置刪除計時
                    if before.channel.id in self.temp_channels_to_monitor:
                        del self.temp_channels_to_monitor[before.channel.id]
                        _log.debug(f"臨時頻道 '{before.channel.name}' 再次有成員，取消刪除計劃。")


    async def _create_and_move_to_temp_channel(self, member, creation_channel):
        guild = creation_channel.guild
        category = creation_channel.category 

        new_channel_name = f"{member.display_name} 的語音頻道"
        
        try:
            temp_vc = await guild.create_voice_channel(
                name=new_channel_name,
                category=category,
                user_limit=None 
            )
            _log.info(f"為 {member.display_name} 創建了臨時語音頻道: '{temp_vc.name}' (ID: {temp_vc.id})。")

            # 將新創建的頻道 ID 和相關信息儲存到資料庫
            await self.temp_channels_db_collection.insert_one({
                '_id': temp_vc.id,
                'guild_id': guild.id,
                'creator_id': member.id,
                'created_at': datetime.datetime.utcnow(),
                'name': temp_vc.name # 也儲存名稱，方便日誌和除錯
            })
            _log.info(f"臨時頻道 (ID: {temp_vc.id}) 已記錄到資料庫。")

            # 將新創建的頻道 ID 添加到內部監控列表
            self.temp_channels_to_monitor[temp_vc.id] = None 

            await member.move_to(temp_vc)
            _log.info(f"將 {member.display_name} 移動到 '{temp_vc.name}'。")

        except discord.Forbidden:
            _log.error(f"缺少權限無法在 {guild.name} 創建或移動頻道。")
            await creation_channel.send(f"我沒有足夠的權限來為你創建語音頻道。請檢查我的權限。")
        except discord.HTTPException as e:
            _log.error(f"創建或移動語音頻道時發生 HTTP 錯誤: {e}")
            await creation_channel.send(f"創建語音頻道時發生錯誤，請稍後再試。")
        except Exception as e:
            _log.error(f"創建或移動語音頻道時發生未知錯誤: {e}", exc_info=True)
            await creation_channel.send(f"發生未知錯誤，無法創建語音頻道。")

    @tasks.loop(seconds=5.0)
    async def check_empty_temp_channels(self):
        channels_to_delete_from_monitor = []
        current_time = asyncio.get_event_loop().time()

        # 遍歷內部監控列表
        for channel_id, delete_time in list(self.temp_channels_to_monitor.items()):
            channel = self.bot.get_channel(channel_id)

            if channel is None:
                _log.info(f"監控的頻道 {channel_id} (可能已手動刪除) 不存在，從內部監控和資料庫中移除。")
                channels_to_delete_from_monitor.append(channel_id)
                await self.temp_channels_db_collection.delete_one({'_id': channel_id})
                continue
            
            # 如果頻道現在有成員，並且之前設定了刪除時間，則取消刪除
            if channel.members:
                if delete_time is not None:
                    self.temp_channels_to_monitor[channel_id] = None
                    _log.debug(f"頻道 '{channel.name}' (ID: {channel_id}) 再次有成員，取消刪除計劃。")
                continue

            # 如果頻道是空的
            if not channel.members:
                # 如果尚未設置刪除時間，則設置它
                if delete_time is None:
                    self.temp_channels_to_monitor[channel_id] = current_time + self.DELETE_DELAY_SECONDS
                    _log.info(f"頻道 '{channel.name}' (ID: {channel_id}) 變空，設定 {self.DELETE_DELAY_SECONDS} 秒後刪除。")
                # 如果已經設置了刪除時間並且時間已到
                elif current_time >= delete_time:
                    _log.info(f"臨時語音頻道 '{channel.name}' (ID: {channel_id}) 已空且超過延遲，準備刪除。")
                    try:
                        await channel.delete()
                        _log.info(f"成功刪除臨時語音頻道: '{channel.name}' (ID: {channel_id})。")
                        channels_to_delete_from_monitor.append(channel_id)
                        # 從資料庫中移除該頻道的記錄
                        await self.temp_channels_db_collection.delete_one({'_id': channel_id})
                        _log.info(f"臨時頻道 (ID: {channel_id}) 已從資料庫中移除。")
                    except discord.Forbidden:
                        _log.error(f"缺少權限無法刪除臨時語音頻道 '{channel.name}' (ID: {channel_id})。")
                    except discord.HTTPException as e:
                        _log.error(f"刪除臨時語音頻道 '{channel.name}' (ID: {channel_id}) 時發生 HTTP 錯誤: {e}")
                    except Exception as e:
                        _log.error(f"刪除臨時語音頻道時發生未知錯誤: {e}", exc_info=True)
            
        # 從內部監控列表中移除已處理的頻道
        for channel_id in channels_to_delete_from_monitor:
            if channel_id in self.temp_channels_to_monitor:
                del self.temp_channels_to_monitor[channel_id]


    @check_empty_temp_channels.before_loop
    async def before_check_empty_temp_channels(self):
        await self.bot.wait_until_ready()
        _log.info("等待 Bot 準備就緒以啟動臨時語音頻道檢查任務。")

        # --- 啟動時檢查邏輯：只檢查資料庫中記錄的臨時頻道 ---
        if self.temp_channels_db_collection is None:
            _log.error("temp_channels_db_collection is not available at startup. Skipping initial check.")
            return

        _log.info("Bot 啟動時執行初始空臨時語音頻道檢查 (從資料庫讀取)。")
        
        # 從資料庫查詢所有記錄的臨時頻道
        # .to_list(length=None) 用於從異步遊標獲取所有結果
        all_temp_channels_in_db = await self.temp_channels_db_collection.find({}).to_list(length=None)

        for doc in all_temp_channels_in_db:
            channel_id = doc['_id']
            # 從 Discord 緩存中獲取頻道對象
            channel = self.bot.get_channel(channel_id)
            
            if channel and isinstance(channel, discord.VoiceChannel):
                if not channel.members:
                    # 如果頻道存在且為空，則將其添加到內部監控列表，設置為立即過期
                    self.temp_channels_to_monitor[channel.id] = asyncio.get_event_loop().time() 
                    _log.info(f"發現資料庫記錄的空的臨時頻道 '{channel.name}' (ID: {channel.id})，已加入啟動時清理。")
                else:
                    # 如果頻道存在但不空，確保它不會被立即刪除 (如果之前有計時，則取消)
                    self.temp_channels_to_monitor[channel.id] = None 
                    _log.debug(f"資料庫記錄的臨時頻道 '{channel.name}' (ID: {channel.id}) 有成員，確保不被立即刪除。")
            else:
                # 如果資料庫裡有記錄但頻道在 Discord 上不存在了
                _log.info(f"資料庫記錄的臨時頻道 {channel_id} 在 Discord 上不存在，從資料庫中移除。")
                await self.temp_channels_db_collection.delete_one({'_id': channel_id})
        _log.info("啟動時臨時語音頻道檢查完成。")