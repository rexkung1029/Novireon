import discord
import re
import asyncio
import yt_dlp
import time
import logging
import os

from discord.ext import commands
from discord.ui import Button,View
from discord import app_commands
from discord import Interaction as Itat
from discord import ButtonStyle

from googleapiclient.discovery import build



# --- Global Variables and Setup ---
youtube_base_url = 'https://www.youtube.com/'
youtube_watch_url = youtube_base_url + 'watch?v='
yt_dl_options = {"format": "bestaudio/best"}
ytdl = yt_dlp.YoutubeDL(yt_dl_options)
ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=0.3"'
}

voice_clients: dict = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Youtube_Itat_Re")

# Get API key from the .env file
YOUTUBE_API_KEY = os.getenv("GOOGLE")
if not YOUTUBE_API_KEY:
    raise ValueError("YouTube API key not found in .env file or environment variables")

# Initialize the YouTube Data API client
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)


class Views:
    # A button that toggles between Pause and Resume
    class PauseResumeButton(discord.ui.Button):
        def __init__(self, guild_id: int):
            is_paused = voice_clients.get(guild_id, {}).get("is_paused", False)
            
            # Set style and label based on the current state
            style = discord.ButtonStyle.green if is_paused else discord.ButtonStyle.primary
            label = "繼續" if is_paused else "暫停"
            emoji = "▶️" if is_paused else "⏸️"

            super().__init__(style=style, label=label, emoji=emoji)
            self.guild_id = guild_id

        async def callback(self, itat: discord.Interaction):
            guild_data = voice_clients.get(self.guild_id, {})
            client = guild_data.get("client")
            if not client:
                await itat.response.send_message("機器人目前不在頻道中。", ephemeral=True)
                return

            # Perform the action
            if client.is_paused():
                await Function._resume(self.guild_id)
            else:
                await Function._pause(self.guild_id)
            
            # Re-create the view to update the button's appearance and edit the original message
            await itat.response.edit_message(view=ControlView(self.guild_id))

    # Button to skip to the next song
    class SkipButton(discord.ui.Button):
        def __init__(self, guild_id: int):
            super().__init__(style=discord.ButtonStyle.secondary, label="下一首", emoji="⏭️")
            self.guild_id = guild_id

        async def callback(self, itat: discord.Interaction):
            await itat.response.defer()
            await Function._skip(self.guild_id)

    # Button to stop playback and disconnect
    class StopButton(discord.ui.Button):
        def __init__(self, guild_id: int):
            super().__init__(style=discord.ButtonStyle.danger, label="停止", emoji="⏹️")
            self.guild_id = guild_id

        async def callback(self, itat: discord.Interaction):
            await itat.response.defer()
            # We call the main _stop function which handles everything
            await Function._stop(Function, self.guild_id)

    # Your existing Recommend button
    class Recommend(Button):
        def __init__(self, guild_id):
            # No changes needed here, but it will be part of the new ControlView
            try:
                self.itat:Itat = voice_clients[guild_id]["itat"]
                self.if_recommend = voice_clients[guild_id]["if_recommend"]
                label = "自動推薦" if self.if_recommend else '不自動推薦'
                style = ButtonStyle.green if self.if_recommend else ButtonStyle.red
                super().__init__(label=label,style=style)
            except Exception as e:
                print(e,"recommend button")
        async def callback(self, itat:Itat):
            try:
                guild_id = self.itat.guild_id
                voice_clients[guild_id]["if_recommend"] = not voice_clients[guild_id]["if_recommend"]
                msg = "播放完畢後將自動推薦" if voice_clients[guild_id]["if_recommend"] else "播放完畢後不會自動推薦"
                # Respond to the interaction and update the view
                await itat.response.edit_message(view=ControlView(guild_id))
                # Send a temporary message to confirm
                await itat.followup.send(msg, ephemeral=True, delete_after=10)

            except Exception as e:
                print(e,"recommend button")

    class Regret(Button):
        def __init__(self, guild_id):
            self.guild_id = guild_id
            super().__init__(
                label="移出佇列",
                style=discord.ButtonStyle.red
            )

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_message("正在處理", delete_after=10)
            await Function.remove_from_queue(self.guild_id, -1)

# A new View that holds all our control buttons
class ControlView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None) # Timeout=None is crucial so the buttons don't expire
        
        # Add buttons to the view
        self.add_item(Views.PauseResumeButton(guild_id))
        self.add_item(Views.SkipButton(guild_id))
        self.add_item(Views.StopButton(guild_id))
        self.add_item(Views.Recommend(guild_id))




class Youtube(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="play", description="播放音樂")
    @app_commands.describe(link="可使用網址或直接搜尋")
    async def play(self, itat:Itat, link:str):
        try:
            await itat.response.defer(ephemeral=True)
            guild_id = itat.guild_id
            # saving data
            if guild_id in voice_clients:
                voice_clients[guild_id].update({
                    "itat": itat,
                    "command_channel": itat.channel
                    })
            else:
                voice_clients[guild_id]= {
                    "itat": itat,
                    "command_channel": itat.channel
                    }
            if not await Function.voice_channel_check(guild_id):
                return
            url = await Function.url_formatter(Function, guild_id, link)
            if url is None:
                # This can happen if search is initiated, which has its own flow.
                return
            if youtube_watch_url not in url:
                await itat.followup.send("無效的連結或關鍵字")
                return

            if "client" not in voice_clients[guild_id] or not voice_clients[guild_id]["client"].is_connected():
                await Function._play(guild_id, url)
            else:
                await Function.queue(guild_id, url)
        except Exception as e:
            print(f"play command error: {e}")

    @app_commands.command(name="list_queue", description="列出佇列中前25首歌曲")
    async def list_queue(self,itat:Itat):
        try:
            await itat.response.defer()
            guild_id = itat.guild_id
            voice_clients[guild_id]["itat"] = itat
            if not await Function.voice_channel_check(guild_id):
                return

            queue = voice_clients[guild_id].get("queue", [])
            if not queue:
                await itat.followup.send("佇列為空", ephemeral=True)
                return

            embed = discord.Embed(title="播放佇列", color=0xadc8ff)
            for item in queue[:25]:
                title = item["title"]
                author = item["author"]
                embed.add_field(name=title, value=f"by {author}", inline=False)

            await itat.followup.send(embed=embed)
        except Exception as e:
            print(f"list_queue error: {e}")

    @app_commands.command(name="stop", description="停止播放並刪除佇列等")
    async def stop(self, itat:Itat):
        try:
            await itat.response.defer()
            guild_id = itat.guild_id
            voice_clients[guild_id]["itat"] = itat
            if not await Function.voice_channel_check(guild_id):
                return
            await Function._stop(Function, guild_id)
        except Exception as e:
            print(f"stop command error: {e}")

    @app_commands.command(name="skip")
    async def skip(self, itat:Itat):
        await itat.response.defer()
        guild_id = itat.guild_id
        await Function._skip(guild_id)

    @app_commands.command(name="pause", description="暫停目前播放的音樂")
    async def pause(self, itat: Itat):
        await itat.response.defer(ephemeral=True)
        guild_id = itat.guild_id
        await Function._pause(guild_id)
        
    @app_commands.command(name="resume", description="恢復播放音樂")
    async def resume(self, itat: Itat):
        await itat.response.defer(ephemeral=True)
        guild_id = itat.guild_id
        await Function._resume(guild_id)

async def setup(bot: commands.Bot):
    await bot.add_cog(Youtube(bot))


class Function():

    async def remove_from_queue(guild_id, index:int):
        try:
            queue = voice_clients[guild_id]["queue"]
            itat:Itat = voice_clients[guild_id]["itat"]
            removed_song = queue.pop(index)
            title = removed_song["title"]
            author = removed_song["author"]
            await itat.followup.send(f"已移除歌曲: {title} by {author}")
        except Exception as e:
            print(f"remove_from_queue error: {e}")

    async def play_next(self, guild_id):
        try:
            if guild_id not in voice_clients:
                return

            command_channel:discord.TextChannel = voice_clients[guild_id]["command_channel"]

            embed_msg = voice_clients[guild_id].get("embed_msg")
            embed = voice_clients[guild_id].get("embed")
            embed.description = '播放完畢'
            await embed_msg.edit(embed=embed, view=None)

            if len(voice_clients[guild_id].get("queue", [])) > 0:
                next_url = voice_clients[guild_id]["queue"].pop(0)["url"]
                await Function._play(guild_id, url=next_url)
            elif voice_clients[guild_id].get("if_recommend"):
                current_url = voice_clients[guild_id].get("url")
                next_url = await Function.get_youtube_recommendation(guild_id, current_url)
                if next_url:
                    await Function._play(guild_id, url=next_url)
                else:
                    await command_channel.send("無法找到推薦歌曲，播放結束。")
                    await Function._stop(Function, guild_id)
            else:
                await Function._stop(Function, guild_id)
        except Exception as e:
            print(f"play_next error: {e}")
            await Function._stop(Function, guild_id)
            await voice_clients[guild_id]["command_channel"].send("播放下一首時出現問題")

    async def _play(guild_id, url):
        try:
            itat:Itat = voice_clients[guild_id]["itat"]
            command_channel:discord.TextChannel = voice_clients[guild_id]["command_channel"]
            loop = asyncio.get_event_loop()

            await command_channel.send("正在載入...", delete_after=10)
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

            song_url = data['url']
            title = data['title']
            duration = data['duration']
            thumbnail = data.get('thumbnail', '')

            if "client" not in voice_clients[guild_id] or not voice_clients[guild_id]["client"].is_connected():
                voice_client = await itat.user.voice.channel.connect()
                voice_clients[guild_id]["client"] = voice_client
                voice_clients[guild_id].update({
                    "if_recommend": False,
                    "queue": [],
                    "played": []
                })

            voice_clients[guild_id].update({
                "start_time": time.time(),
                "duration": duration,
                "url": url,
                "itat": itat,
                "is_paused": False,
                "pause_time": 0,
                "total_paused_duration": 0

            })

            played = voice_clients[guild_id]["played"]
            played.append(url)
            if len(played) > 50:
                voice_clients[guild_id]["played"] = played[-50:]

            def after_play(error):
                if error:
                    print(f'Player error: {error}')
                future = asyncio.run_coroutine_threadsafe(Function.play_next(Function, guild_id), loop)
                try:
                    future.result()
                except Exception as e:
                    print(f"Error in after_play callback: {e}")

            player = discord.FFmpegOpusAudio(song_url, **ffmpeg_options)
            voice_clients[guild_id]["client"].play(player, after=after_play)

            embed = discord.Embed(title=title, description="播放中...", color=0xadc8ff)
            embed.set_thumbnail(url=thumbnail)
            view = ControlView(guild_id)
            embed_msg = await command_channel.send(view=view, embed=embed)

            voice_clients[guild_id].update({"embed": embed, "embed_msg": embed_msg})
            voice_clients[guild_id]['progress_task'] = asyncio.create_task(Function.update_progress_bar(guild_id))

        except Exception as e:
            await voice_clients[guild_id]["command_channel"].send("無法播放，請使用連結或再試一次")
            print(f"_play error: {e}")

    async def queue(guild_id, url):
        try:
            command_channel:discord.TextChannel = voice_clients[guild_id]["command_channel"]
            if youtube_watch_url not in url:
                await command_channel.send("無效的連結或關鍵字")
                return

            data = await asyncio.to_thread(ytdl.extract_info, url=url, download=False)
            title = data.get('title', 'Unknown Title')
            thumbnail = data.get('thumbnail', '')
            duration = data['duration']
            author = data.get('uploader', 'Unknown Artist')

            embed = discord.Embed(color=0x28ff28, title=f"加入佇列: {title}", description=f"by {author}")
            embed.set_thumbnail(url=thumbnail)
            embed.add_field(name="時長", value=Function.format_time(duration))

            voice_clients[guild_id]["queue"].append({
                "url": url, "title": title, "thumbnail": thumbnail, "author": author
            })

            view = View()
            view.add_item(Views.Regret(guild_id))
            await command_channel.send(embed=embed, view=view)
        except Exception as e:
            print(f"queue error: {e}")

    def get_youtube_video_id(url: str) -> str | None:
        """
        從各種格式的 YouTube 網址中提取 Video ID。

        Args:
            url: YouTube 網址字串。

        Returns:
            如果成功提取，則回傳 11 個字元的 Video ID 字串。
            如果找不到或格式不符，則回傳 None。
        """
        if not isinstance(url, str):
            return None
            
        # 正規表示式，匹配各種 YouTube 網址格式
        # 解說請見下方
        regex_pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|embed\/|v\/|shorts\/|live\/)?([a-zA-Z0-9_-]{11})'
        
        match = re.search(regex_pattern, url)
        
        if match:
            return match.group(1)
        
        return None

    async def url_formatter(self, guild_id, link):
        video_id = Function.get_youtube_video_id(link)
        if video_id:
            return youtube_watch_url + video_id
        else:
            await self.search(self, guild_id, link)
            return None # Search will handle the rest of the interaction

    async def search(self, guild_id, link):
        try:
            itat:Itat = voice_clients[guild_id]["itat"]
            await itat.followup.send(f"正在搜尋: `{link}`...", ephemeral=True)

            results = await Function.get_youtube_search_results(link, max_results=10)
            if not results:
                await itat.followup.send("找不到任何結果。", ephemeral=True)
                return

            video_opt = [
                discord.SelectOption(
                    label=title[:100],
                    description=f"by {author}"[:100],
                    value=url
                ) for url, title, author in results
            ]
            search_menu = discord.ui.Select(
                placeholder="選擇一首歌",
                options=video_opt,
                min_values=1,
                max_values=1
            )
            view = View()
            view.add_item(search_menu)

            original_message = await itat.followup.send(content="請從下方選擇一個結果", view=view, ephemeral=True)

            async def search_menu_callback(s_itat:Itat):
                try:
                    video_url = s_itat.data['values'][0]
                    await original_message.edit(content="處理中...", view=None)

                    if "client" not in voice_clients[guild_id] or not voice_clients[guild_id]["client"].is_connected():
                        await Function._play(guild_id, video_url)
                    else:
                        await Function.queue(guild_id, video_url)
                except Exception as e:
                    print(f"search_callback error: {e}")

            search_menu.callback = search_menu_callback
        except Exception as e:
            print(f"search error: {e}")
            await itat.followup.send("搜尋時發生錯誤，請使用有效連結或再試一次。", ephemeral=True)

    def format_time(seconds):
        mins, secs = divmod(int(seconds), 60)
        return f"{mins}:{secs:02}"

    def generate_progress_bar(self, guild_id):
        try:
            guild_data = voice_clients[guild_id]
            start_time = guild_data["start_time"]
            duration = guild_data["duration"]
            total_paused_duration = guild_data.get("total_paused_duration", 0)

            if duration == 0: return ""

            # Determine elapsed time based on pause state
            if guild_data.get("is_paused", False):
                # If paused, elapsed time is frozen at the moment of pausing
                pause_time = guild_data.get("pause_time", start_time)
                elapsed = int(pause_time - start_time - total_paused_duration)
            else:
                # If playing, calculate current elapsed time, accounting for all previous pauses
                elapsed = int(time.time() - start_time - total_paused_duration)
            
            progress = min(elapsed / duration, 1.0)
            length = 20
            filled_length = int(length * progress)
            bar = '─' * filled_length + '•' + '─' * (length - filled_length - 1)

            return f"`[{bar}]` `({Function.format_time(elapsed)}/{Function.format_time(duration)})`"
        except (KeyError, ZeroDivisionError, TypeError):
            # Return empty string if data is missing, to prevent crashes
            return ""

    async def voice_channel_check(guild_id):
        try:
            itat:Itat = voice_clients[guild_id]["itat"]
            if not itat.user.voice or not itat.user.voice.channel:
                await itat.followup.send("請先加入一個語音頻道", ephemeral=True)
                return False

            if "client" in voice_clients[guild_id] and voice_clients[guild_id]["client"].is_connected():
                if itat.user.voice.channel.id != voice_clients[guild_id]["client"].channel.id:
                    await itat.followup.send("請加入機器人所在的頻道", ephemeral=True)
                    return False
            return True
        except Exception as e:
            logger.error(f"voice_channel_check error: {e}")
            return False

    async def get_youtube_recommendation(guild_id, url):
        try:
            video_id = Function.get_youtube_video_id(url)
            if not video_id:
                return None

            loop = asyncio.get_event_loop()
            request = youtube.search().list(
                part="snippet",
                relatedToVideoId=video_id,
                type="video",
                maxResults=10
            )
            response = await loop.run_in_executor(None, request.execute)

            played_urls = voice_clients[guild_id].get("played", [])
            for item in response.get("items", []):
                rec_video_id = item["id"]["videoId"]
                rec_url = youtube_watch_url + rec_video_id
                if rec_url not in played_urls:
                    return rec_url

            if response.get("items"):
                return youtube_watch_url + response["items"][0]["id"]["videoId"]

            return None
        except Exception as e:
            print(f"get_youtube_recommendation error: {e}")
            return None

    async def _stop(self, guild_id):
        try:
            if guild_id not in voice_clients:
                return

            if 'progress_task' in voice_clients[guild_id]:
                voice_clients[guild_id]['progress_task'].cancel()
            
            client = voice_clients[guild_id].get("client")
            if client and client.is_connected():
                client.stop()
                await client.disconnect(force=True)
                await voice_clients[guild_id]["command_channel"].send("已停止並斷開連接")

            del voice_clients[guild_id]
        except Exception as e:
            print(f"_stop error: {e}")
            if guild_id in voice_clients:
                 del voice_clients[guild_id]

    async def update_progress_bar(guild_id):
        try:
            # The loop now runs as long as the bot is active in the guild.
            # It will be broken internally or cancelled by the _stop command.
            while guild_id in voice_clients:
                guild_data = voice_clients.get(guild_id)
                if not guild_data: break

                client = guild_data.get("client")
                if not client: break

                # --- START: CORE LOGIC FIX ---
                # The primary loop condition is gone. We now check the state inside.
                # If the song is not playing AND it's not paused, it means the song
                # has finished naturally. The loop for this track is over.
                if not client.is_playing() and not client.is_paused():
                    break
                
                # If the client is paused, we simply wait and check again.
                # We don't update the progress bar.
                if client.is_paused():
                    await asyncio.sleep(1)
                    continue
                # --- END: CORE LOGIC FIX ---

                # If we reach here, it means the client is actively playing.
                embed_msg = guild_data.get("embed_msg")
                embed = guild_data.get("embed")

                if embed and embed_msg:
                    new_progress_bar = Function.generate_progress_bar(Function, guild_id)
                    if embed.description != new_progress_bar:
                        embed.description = new_progress_bar
                        view = ControlView(guild_id)
                        try:
                            await embed_msg.edit(embed=embed, view=view)
                        except discord.NotFound:
                            break # Stop trying if the message was deleted
                
                # Wait for the next update cycle
                await asyncio.sleep(5)
            
            # This final block now executes correctly when the loop breaks
            # because a song finished.
            guild_data = voice_clients.get(guild_id)
            if guild_data:
                embed_msg = guild_data.get("embed_msg")
                embed = guild_data.get("embed")
                if embed_msg and embed:
                    try:
                        embed.description = "播放完畢"
                        await embed_msg.edit(embed=embed, view=None)
                    except discord.NotFound:
                        logger.info(f"Could not find embed for guild {guild_id} to mark '播放完畢'.")
                    except Exception as e:
                        logger.error(f"Failed to edit final embed for guild {guild_id}: {e}")

        except asyncio.CancelledError:
            # This is triggered by _stop(), which is an expected way to exit.
            pass
        except KeyError:
            # This can happen if the guild_data is deleted mid-loop.
            pass 
        except Exception as e:
            logger.error(f"update_progress_bar encountered a fatal error: {e}")

    @staticmethod
    async def get_youtube_search_results(search_query: str, max_results: int = 10):
        try:
            loop = asyncio.get_event_loop()
            request = youtube.search().list(
                q=search_query,
                part="snippet",
                maxResults=max_results,
                type="video",
                relevanceLanguage="zh-TW",
                regionCode="TW"
            )
            response = await loop.run_in_executor(None, request.execute)

            results = []
            for item in response.get("items", []):
                video_id = item["id"]["videoId"]
                title = item["snippet"]["title"]
                author = item["snippet"]["channelTitle"]
                video_url = youtube_watch_url + video_id
                results.append([video_url, title, author])
            return results
        except Exception as e:
            logging.error(f"get_youtube_search_results error: {e}")
            return []

    @staticmethod
    async def _pause(guild_id: int) -> bool:
        try:
            itat:Itat = voice_clients[guild_id]["itat"]
            if not await Function.voice_channel_check(guild_id):
                return

            guild_data = voice_clients.get(guild_id, {})
            client = guild_data.get("client")

            # Check if music is playing and is not already paused
            if client and client.is_playing() and not guild_data.get("is_paused"):
                client.pause()
                voice_clients[guild_id]["is_paused"] = True
                voice_clients[guild_id]["pause_time"] = time.time()
                
                # --- ADDED FOR IMMEDIATE FEEDBACK ---
                # Update the embed once to show the paused state immediately
                try:
                    embed = voice_clients[guild_id]["embed"]
                    embed.description = "已暫停"
                    await voice_clients[guild_id]["embed_msg"].edit(embed=embed)
                except Exception as e:
                    logger.warning(f"Could not edit embed on pause for guild {guild_id}: {e}")
                # ------------------------------------

                await itat.followup.send("音樂已暫停", ephemeral=True)
            else:
                await itat.followup.send("沒有正在播放的音樂，或音樂已被暫停。", ephemeral=True)
        except Exception as e:
            print(f"pause command error: {e}")

    @staticmethod
    async def _resume(guild_id: int) -> bool:
        try:
            itat:Itat = voice_clients[guild_id]["itat"]
            if not await Function.voice_channel_check(guild_id):
                return
            
            guild_data = voice_clients.get(guild_id, {})
            client = guild_data.get("client")

            if client and guild_data.get("is_paused"):
                client.resume()
                paused_for = time.time() - guild_data["pause_time"]
                voice_clients[guild_id]["total_paused_duration"] += paused_for
                voice_clients[guild_id]["is_paused"] = False
                await itat.followup.send("音樂已恢復播放", ephemeral=True)
            else:
                await itat.followup.send("音樂未被暫停", ephemeral=True)
        except Exception as e:
            print(f"resume command error: {e}")

    @staticmethod
    async def _skip(guild_id: int) -> bool:
        """Skips the current song for a guild. Returns True on success."""
        try:
            itat:Itat = voice_clients[guild_id]["itat"]
            if not await Function.voice_channel_check(guild_id):
                return
            if voice_clients[guild_id].get("client") and voice_clients[guild_id]["client"].is_playing():
                voice_clients[guild_id]["client"].stop()
            else:
                await itat.followup.send("沒有正在播放的音樂", ephemeral=True)
        except Exception as e:
            await itat.followup.send("播放下一首時出現問題", ephemeral=True)
            await Function._stop(Function, guild_id)
            print(f"skip command error: {e}")
    