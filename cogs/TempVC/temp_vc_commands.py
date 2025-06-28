# your_bot_project/cogs/TempVC/temp_vc_commands.py
import discord
from discord.ext import commands, tasks
import logging
import asyncio
import datetime

from Utils import db_helper 

_log = logging.getLogger(__name__)

class TempVCCommands(commands.Cog):
    """
    提供自動創建和管理臨時語音頻道的核心功能。
    """

    def __init__(self, bot):
        self.bot = bot
        self.temp_channels_to_monitor = {} 
        self.DELETE_DELAY_SECONDS = 30 
        
        self.guild_config_collection = db_helper.get_collection('guild_configs')
        if self.guild_config_collection is None:
            _log.error("Failed to get 'guild_configs' collection for TempVCCommands. DB might not be connected.")

        self.temp_channels_db_collection = db_helper.get_collection('temp_channels')
        if self.temp_channels_db_collection is None:
            _log.error("Failed to get 'temp_channels' collection for TempVCCommands. DB might not be connected.")

        self.check_empty_temp_channels.start()
        _log.info("TempVCCommands Cog initialized and background task started.")

    def cog_unload(self):
        self.check_empty_temp_channels.cancel()
        _log.info("TempVCCommands Cog unloaded and background task cancelled.")

    # --- 公共函數，供 Watcher 調用 ---
    async def handle_create_temp_channel_request(self, member, creation_channel):
        """
        處理創建臨時頻道的請求。由 Watcher 調用。
        """
        await self._create_and_move_to_temp_channel(member, creation_channel)
        
    async def handle_member_leave_channel(self, member, channel_left):
        """
        處理成員離開頻道事件。由 Watcher 調用。
        檢查是否為臨時頻道，並根據剩餘人數（不計機器人）決定是否啟動刪除機制。
        """
        if self.temp_channels_db_collection is None:
            _log.warning(f"handle_member_leave_channel: DB collection not available for {member.guild.name}.")
            return

        # 檢查離開的頻道是否是 Bot 創建的臨時頻道 (從資料庫中查找)
        is_temp_channel_in_db = await self.temp_channels_db_collection.find_one({'_id': channel_left.id})
        
        if is_temp_channel_in_db:
            _log.info(f"[TempVC] {member.display_name} 離開了臨時頻道 '{channel_left.name}' (ID: {channel_left.id}, 由資料庫識別)。")
            
            # 獲取頻道中非機器人成員的數量
            human_members_in_channel = [m for m in channel_left.members if not m.bot]
            num_human_members = len(human_members_in_channel)

            if num_human_members == 0: 
                # 頻道中已無人類成員，設置刪除計時
                # 只有當頻道實際變為空（無人類）時才設置或更新刪除計時
                if channel_left.id not in self.temp_channels_to_monitor or \
                   self.temp_channels_to_monitor[channel_left.id] is None:
                    self.temp_channels_to_monitor[channel_left.id] = asyncio.get_event_loop().time() + self.DELETE_DELAY_SECONDS
                    _log.info(f"臨時頻道 '{channel_left.name}' (ID: {channel_left.id}) 已無人類成員，將在 {self.DELETE_DELAY_SECONDS} 秒後檢查刪除。")
            else:
                # 頻道中仍有人類成員，取消刪除計時 (如果存在)
                if channel_left.id in self.temp_channels_to_monitor:
                    del self.temp_channels_to_monitor[channel_left.id]
                    _log.debug(f"臨時頻道 '{channel_left.name}' (ID: {channel_left.id}) 仍有 {num_human_members} 個人類成員，取消刪除計劃。")
        else:
            _log.debug(f"[TempVC] {member.display_name} 離開了非臨時頻道 '{channel_left.name}'。")

    # --- 內部函數，不直接暴露為公共 API ---
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

            await self.temp_channels_db_collection.insert_one({
                '_id': temp_vc.id,
                'guild_id': guild.id,
                'creator_id': member.id,
                'created_at': datetime.datetime.utcnow(),
                'name': temp_vc.name 
            })
            _log.info(f"臨時頻道 (ID: {temp_vc.id}) 已記錄到資料庫。")

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
        """
        背景任務，定期檢查所有被監控的臨時語音頻道是否為空（無人類成員），並在滿足條件時刪除。
        """
        channels_to_delete_from_monitor = []
        current_time = asyncio.get_event_loop().time()

        for channel_id, delete_time in list(self.temp_channels_to_monitor.items()):
            channel = self.bot.get_channel(channel_id)

            if channel is None:
                _log.info(f"監控的頻道 {channel_id} (可能已手動刪除) 不存在，從內部監控和資料庫中移除。")
                channels_to_delete_from_monitor.append(channel_id)
                if self.temp_channels_db_collection is not None:
                    await self.temp_channels_db_collection.delete_one({'_id': channel_id})
                continue
            
            # 獲取頻道中非機器人成員的數量
            human_members_in_channel = [m for m in channel.members if not m.bot]
            num_human_members = len(human_members_in_channel)

            # 如果頻道現在有人類成員，並且之前設定了刪除時間，則取消刪除
            if num_human_members > 0:
                if delete_time is not None:
                    self.temp_channels_to_monitor[channel.id] = None
                    _log.debug(f"頻道 '{channel.name}' (ID: {channel.id}) 再次有 {num_human_members} 個人類成員，取消刪除計劃。")
                continue # 頻道不空，跳過

            # 如果頻道是空的 (無人類成員)
            if num_human_members == 0:
                # 如果尚未設置刪除時間，則設置它
                if delete_time is None:
                    self.temp_channels_to_monitor[channel.id] = current_time + self.DELETE_DELAY_SECONDS
                    _log.info(f"頻道 '{channel.name}' (ID: {channel_id}) 已無人類成員，設定 {self.DELETE_DELAY_SECONDS} 秒後刪除。")
                # 如果已經設置了刪除時間並且時間已到
                elif current_time >= delete_time:
                    _log.info(f"臨時語音頻道 '{channel.name}' (ID: {channel_id}) 已空（無人類成員）且超過延遲，準備刪除。")
                    try:
                        await channel.delete()
                        _log.info(f"成功刪除臨時語音頻道: '{channel.name}' (ID: {channel_id})。")
                        channels_to_delete_from_monitor.append(channel_id)
                        if self.temp_channels_db_collection is not None:
                            await self.temp_channels_db_collection.delete_one({'_id': channel_id})
                            _log.info(f"臨時頻道 (ID: {channel_id}) 已從資料庫中移除。")
                    except discord.Forbidden:
                        _log.error(f"缺少權限無法刪除臨時語音頻道 '{channel.name}' (ID: {channel_id})。")
                    except discord.HTTPException as e:
                        _log.error(f"刪除臨時語音頻道 '{channel.name}' (ID: {channel_id}) 時發生 HTTP 錯誤: {e}")
                    except Exception as e:
                        _log.error(f"刪除臨時語音頻道時發生未知錯誤: {e}", exc_info=True)
            
        for channel_id in channels_to_delete_from_monitor:
            if channel_id in self.temp_channels_to_monitor:
                del self.temp_channels_to_monitor[channel_id]


    @check_empty_temp_channels.before_loop
    async def before_check_empty_temp_channels(self):
        await self.bot.wait_until_ready()
        _log.info("等待 Bot 準備就緒以啟動臨時語音頻道檢查任務。")

        if self.temp_channels_db_collection is None:
            _log.error("temp_channels_db_collection is not available at startup. Skipping initial check.")
            return

        _log.info("Bot 啟動時執行初始空臨時語音頻道檢查 (從資料庫讀取)。")
        
        all_temp_channels_in_db = await self.temp_channels_db_collection.find({}).to_list(length=None)

        for doc in all_temp_channels_in_db:
            channel_id = doc['_id']
            channel = self.bot.get_channel(channel_id)
            
            if channel and isinstance(channel, discord.VoiceChannel):
                # 檢查頻道中是否還有人類成員
                human_members_in_channel = [m for m in channel.members if not m.bot]
                num_human_members = len(human_members_in_channel)

                if num_human_members == 0:
                    self.temp_channels_to_monitor[channel.id] = asyncio.get_event_loop().time() 
                    _log.info(f"發現資料庫記錄的空的臨時頻道 '{channel.name}' (ID: {channel.id})，已加入啟動時清理。")
                else:
                    self.temp_channels_to_monitor[channel.id] = None 
                    _log.debug(f"資料庫記錄的臨時頻道 '{channel.name}' (ID: {channel.id}) 仍有 {num_human_members} 個人類成員，確保不被立即刪除。")
            else:
                _log.info(f"資料庫記錄的臨時頻道 {channel_id} 在 Discord 上不存在，從資料庫中移除。")
                await self.temp_channels_db_collection.delete_one({'_id': channel_id})
        _log.info("啟動時臨時語音頻道檢查完成。")