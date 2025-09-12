import discord
from discord import app_commands
from discord.ext import commands

import asyncio
import datetime
import os
import psutil
import time


class PingCommands:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.process = psutil.Process(os.getpid())

    def get_latency_color(self, latency_ms: float) -> discord.Color:
        if latency_ms < 80:
            return discord.Color.green()
        elif latency_ms < 150:
            return discord.Color.yellow()
        else:
            return discord.Color.red()

    def format_uptime(self, uptime_delta: datetime.timedelta) -> str:
        days = uptime_delta.days
        hours, rem = divmod(uptime_delta.seconds, 3600)
        minutes, seconds = divmod(rem, 60)

        parts = []
        if days > 0:
            parts.append(f"{days} 天")
        if hours > 0:
            parts.append(f"{hours} 小時")
        if minutes > 0:
            parts.append(f"{minutes} 分鐘")
        parts.append(f"{seconds} 秒")

        return " ".join(parts)

    @app_commands.command(name="ping", description="顯示機器人與伺服器的即時狀態")
    async def ping(self, itat: discord.Interaction):
        start_time = time.monotonic()
        await itat.response.send_message("正在獲取詳細狀態...", ephemeral=True)
        end_time = time.monotonic()
        msg_latency = (end_time - start_time) * 1000

        api_latency = self.bot.latency * 1000
        voice_latency = (
            itat.guild.voice_client.latency * 1000
            if itat.guild and itat.guild.voice_client
            else None
        )

        server_cpu_usage = await asyncio.to_thread(psutil.cpu_percent, interval=1)

        server_memory = psutil.virtual_memory()
        server_memory_used_gb = server_memory.used / (1024**3)
        server_memory_total_gb = server_memory.total / (1024**3)
        server_memory_percent = server_memory.percent

        bot_memory_usage_mb = self.process.memory_info().rss / (1024**2)

        uptime = (
            self.format_uptime(datetime.datetime.utcnow() - self.bot.start_time)
            if hasattr(self.bot, "start_time")
            else "N/A"
        )

        embed_color = self.get_latency_color(api_latency)
        embed = discord.Embed(
            title="機器人與主機狀態報告",
            color=embed_color,
            timestamp=datetime.datetime.utcnow(),
        )

        latency_info = (
            f"**API 延遲:** `{api_latency:.2f} ms`\n"
            f"**訊息來回:** `{msg_latency:.2f} ms`"
        )
        if voice_latency is not None:
            latency_info += f"\n**語音延遲:** `{voice_latency:.2f} ms`"
        embed.add_field(name="網路延遲", value=latency_info, inline=True)

        host_info = (
            f"**CPU 總負載:** `{server_cpu_usage:.1f}%`\n"
            f"**記憶體用量:** `{server_memory_used_gb:.2f} / {server_memory_total_gb:.2f} GB` (`{server_memory_percent}%)`"
        )
        embed.add_field(name="伺服器主機狀態", value=host_info, inline=True)

        bot_info = (
            f"**程序記憶體:** `{bot_memory_usage_mb:.2f} MB`\n"
            f"**已運行時間:** `{uptime}`"
        )
        embed.add_field(name="機器人自身狀態", value=bot_info, inline=False)

        embed.set_footer(
            text=f"由 {itat.user.display_name} 請求",
            icon_url=itat.user.avatar.url if itat.user.avatar else None,
        )

        await itat.edit_original_response(content=None, embed=embed)
