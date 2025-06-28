import discord
from discord.ext import commands
import logging

# 假設 TempVCCommands 會提供一個註冊機制或是一個全局可訪問的實例
# 我們會通過 bot.get_cog() 來獲取 TempVCCommands 的實例
# from cogs.TempVC import temp_vc_commands # 這裡不直接導入類，而是通過 bot.get_cog()

_log = logging.getLogger(__name__)

class VoiceChannelWatcher(commands.Cog):
    """
    監聽語音頻道狀態更新，並觸發相關模組的處理邏輯。
    """

    def __init__(self, bot):
        self.bot = bot
        _log.info("VoiceChannelWatcher Cog initialized.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        temp_vc_cog = self.bot.get_cog("TempVCCommands") 
        if temp_vc_cog is None:
            _log.warning("TempVCCommands Cog 未載入，語音頻道事件無法處理。")
            return
        
        guild_id = member.guild.id
        creation_channel_id = None
        if temp_vc_cog.guild_config_collection is not None: 
            config_doc = await temp_vc_cog.guild_config_collection.find_one({'_id': guild_id})
            if config_doc:
                creation_channel_id = config_doc.get('temp_vc_creation_channel_id')
        
        # --- 新增的日誌，幫助排查 ---
        _log.debug(f"[Watcher] on_voice_state_update triggered for {member.display_name} (ID: {member.id}).")
        _log.debug(f"[Watcher] Before Channel: {before.channel.name if before.channel else 'None'} (ID: {before.channel.id if before.channel else 'None'})")
        _log.debug(f"[Watcher] After Channel: {after.channel.name if after.channel else 'None'} (ID: {after.channel.id if after.channel else 'None'})")
        _log.debug(f"[Watcher] Configured creation_channel_id for guild {guild_id}: {creation_channel_id}.")


        # --- 處理創建臨時頻道 (用戶進入創建頻道) ---
        # 條件 1: 用戶進入了某個頻道
        # 條件 2: 進入的頻道 ID 與資料庫中設定的創建頻道 ID 相符
        # 條件 3: 用戶是從其他頻道或沒有頻道狀態進入的 (不是在同一個頻道內改變狀態)
        if after.channel and after.channel.id == creation_channel_id:
            _log.debug(f"[Watcher] Condition 1 (after.channel & after.channel.id == creation_channel_id) MET.")
            if before.channel != after.channel:
                _log.info(f"[Watcher] {member.display_name} 從 {before.channel.name if before.channel else '無頻道'} 加入了創建頻道 '{after.channel.name}' (ID: {creation_channel_id})。觸發創建。")
                await temp_vc_cog.handle_create_temp_channel_request(member, after.channel)
                return 
            else:
                _log.debug(f"[Watcher] Condition 3 (before.channel != after.channel) NOT MET. User state changed in same channel (e.g., mute/unmute).")
        else:
            _log.debug(f"[Watcher] Condition 1 (after.channel & after.channel.id == creation_channel_id) NOT MET. No creation triggered.")


        # --- 處理刪除臨時頻道 (用戶離開語音頻道) ---
        # 僅當用戶從一個頻道離開到另一個頻道（或離開所有頻道）時才執行此邏輯
        if before.channel and before.channel != after.channel:
            _log.info(f"[Watcher] {member.display_name} 離開了頻道 '{before.channel.name}' (ID: {before.channel.id})。觸發檢查刪除。")
            await temp_vc_cog.handle_member_leave_channel(member, before.channel)
        else:
            _log.debug(f"[Watcher] No channel leaving event (before.channel or before.channel == after.channel). No deletion check triggered.")


# setup 函數將 VoiceChannelWatcher Cog 添加到 Bot 中
async def setup(bot):
    await bot.add_cog(VoiceChannelWatcher(bot))
    _log.info("VoiceChannelWatcher Cog loaded successfully.")