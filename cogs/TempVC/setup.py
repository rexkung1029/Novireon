# your_bot_project/cogs/TempVC/setup.py
import discord
from discord.ext import commands
import logging

from Utils import db_helper # 導入資料庫輔助模組

_log = logging.getLogger(__name__)

class TempVCSetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 獲取用於儲存伺服器配置的集合
        self.guild_config_collection = db_helper.get_collection('guild_configs')
        if self.guild_config_collection is None:
            _log.error("Failed to get 'guild_configs' collection. DB might not be connected.")

    @commands.group(name="tempvcset", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True) # 只有有管理頻道權限的人才能使用
    async def tempvcset(self, ctx):
        """
        管理臨時語音頻道設定。
        需要 '管理頻道' 權限。
        """
        await ctx.send_help(ctx.command)

    @tempvcset.command(name="channel")
    async def tempvcset_channel(self, ctx, channel: discord.VoiceChannel = None):
        """
        設定或查詢用於創建臨時語音頻道的頻道。

        `channel`: 指定一個語音頻道。如果未提供，則顯示當前設定的頻道。
        範例:
        `!tempvcset channel "創建語音頻道"` - 將 "創建語音頻道" 設定為創建頻道
        `!tempvcset channel` - 顯示當前設定的頻道
        """
        if self.guild_config_collection is None:
            await ctx.send("資料庫服務不可用，無法設定。")
            return

        guild_id = ctx.guild.id

        if channel:
            # 設定頻道 ID 到資料庫
            await self.guild_config_collection.update_one(
                {'_id': guild_id},
                {'$set': {'temp_vc_creation_channel_id': channel.id}},
                upsert=True
            )
            await ctx.send(f"已將語音頻道 **{channel.name}** 設定為臨時語音頻道創建入口。")
            _log.info(f"伺服器 {ctx.guild.name} (ID: {guild_id}) 已將臨時語音頻道創建入口設定為 {channel.name} (ID: {channel.id})。")
        else:
            # 查詢當前設定的頻道 ID
            config_doc = await self.guild_config_collection.find_one({'_id': guild_id})
            
            if config_doc and 'temp_vc_creation_channel_id' in config_doc:
                channel_id = config_doc['temp_vc_creation_channel_id']
                current_channel = ctx.guild.get_channel(channel_id)
                if current_channel:
                    await ctx.send(f"當前設定的臨時語音頻道創建入口是：**{current_channel.name}** (ID: {current_channel.id})。")
                else:
                    await ctx.send(f"當前設定的頻道 (ID: {channel_id}) 似乎已不存在，請重新設定。")
            else:
                await ctx.send("目前尚未設定臨時語音頻道創建入口。請使用 `!tempvcset channel <頻道名稱或ID>` 來設定。")

    @tempvcset.command(name="clear")
    async def tempvcset_clear(self, ctx):
        """
        清除用於創建臨時語音頻道的頻道設定。
        """
        if self.guild_config_collection is None:
            await ctx.send("資料庫服務不可用，無法清除設定。")
            return

        guild_id = ctx.guild.id
        # 從資料庫中移除該欄位
        await self.guild_config_collection.update_one(
            {'_id': guild_id},
            {'$unset': {'temp_vc_creation_channel_id': ""}} # $unset 操作符用於刪除欄位
        )
        await ctx.send("已清除臨時語音頻道創建入口的設定。")
        _log.info(f"伺服器 {ctx.guild.name} (ID: {guild_id}) 已清除臨時語音頻道創建入口設定。")


# setup 函數用於載入此 Cog
async def setup(bot):
    await bot.add_cog(TempVCSetup(bot))
    _log.info("TempVCSetup Cog loaded successfully.")