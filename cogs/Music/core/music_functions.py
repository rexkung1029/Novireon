import asyncio
import discord 
import logging
import time
import os

from discord.ui import View
from discord    import Interaction as Itat
from discord    import VoiceClient as VC
from pymongo    import MongoClient

from mongo_crud          import MongoCRUD
from .                   import music_utils
from ..youtube           import Youtube
from .music_data         import voice_data
from .view.control_views import ControlView


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Music_Function")

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=0.3"'
}

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

class Functions():
    async def _pause(guild_id):
        try:
            client:VC = voice_data[guild_id].get("client")
            data = db_handler.get(query={"_id":guild_id})[0]
            music_channel:discord.TextChannel = voice_data[guild_id]["music_channel"]
            if client and data.get("is_playing"):
                client.pause()
                db_handler.update_many(
                    query={"_id":guild_id},
                    new_values={
                        "is_playing":False,
                        "pause_time":time.time()
                    }
                )
                await music_channel.send("音樂已暫停", delete_after=5)
        except Exception as e:
            logger.error(f"pause command error: {e}")

    async def _play(guild_id):
        try:
            loop = asyncio.get_event_loop()
            music_channel:discord.TextChannel = voice_data[guild_id]["music_channel"]

            def after_play(error):
                if error:
                    logger.info(f'Player error: {error}')
                future = asyncio.run_coroutine_threadsafe(Functions.play_next(guild_id), loop)
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error in after_play callback: {e}")
            
            next_song_data = db_handler.pop(query={"_id":guild_id}, field="queue")

            if "client" not in voice_data[guild_id] or not voice_data[guild_id]["client"].is_connected():
                itat:Itat = voice_data[guild_id]["itat"]
                voice_client:VC = await itat.user.voice.channel.connect()
                voice_data[guild_id]["client"] = voice_client
            else:
                voice_client = voice_data[guild_id]["client"]
            await music_channel.send("正在載入...", delete_after=5)
            
            player = discord.FFmpegOpusAudio(next_song_data['song_url'], **ffmpeg_options)
            voice_client.play(player,after=after_play)

            db_handler.update_one(
                query={"_id":guild_id},
                new_values={
                    "start_time": time.time(),
                    "duration":next_song_data['duration'],
                    "song_url":next_song_data['song_url'],
                    "pause_time": None,
                    "total_paused_duration": None,
                    "is_playing": True
                },
                upsert=True
            )


            embed = discord.Embed(title=next_song_data['title'], description="播放中...", color=0xadc8ff)
            embed.set_thumbnail(url=next_song_data.get('thumbnail', ''))
            control_view = ControlView(guild_id)
            embed_msg = await music_channel.send(view=control_view, embed=embed)
            voice_data[guild_id]["state_embed_message"] = embed_msg

            db_handler.update_one(
                query={"_id":guild_id},
                new_values={
                    "current_playing":next_song_data
                },
                upsert=True
            )

            voice_data[guild_id]['progress_task'] = asyncio.create_task(Functions.playback_status_updater(guild_id))
        except Exception as e:
            await voice_data[guild_id]["music_channel"].send("無法播放，請使用連結或再試一次", delete_after=10)
            logger.error(f"_play error: {e}")

    async def _resume(guild_id):
        try:
            client:VC = voice_data[guild_id].get("client")
            data = db_handler.get(query={"_id":guild_id})[0]   
            music_channel:discord.TextChannel = voice_data[guild_id]["music_channel"]     
            if client and not data.get('is_playing'):
                client.resume()
                paused_for = time.time() - data['pause_time']
                paused_time = data.get('total_paused_duration')
                if paused_time is None : paused_time = 0
                db_handler.update_many(
                    query={'_id':guild_id},
                    new_values={
                        'total_paused_duration': paused_for+paused_time,
                        'is_playing':True
                    }
                )
                await music_channel.send("音樂已恢復播放", delete_after=5)
        except Exception as e:
            print(f"resume command error: {e}")            

    async def _skip(guild_id):
        try:
            client:VC = voice_data[guild_id].get("client")
            data = db_handler.get(query={"_id":guild_id})[0]
            music_channel = voice_data[guild_id].get("music_channel")
            if client and data.get('is_playing'):
                client.stop()
            else:
                await music_channel.send("沒有正在播放的音樂", delete_after=5)
        except Exception as e:
            await music_channel.send("播放下一首時出現問題", delete_after=10)
            await Functions._stop(guild_id)
            logger.error(f"skip command error: {e}")

    async def _stop(guild_id):
        if guild_id not in voice_data:
            return
        
        if "progress_task" not in voice_data[guild_id]:
            return
        
        if "client" not in voice_data[guild_id]:
            return

        voice_data[guild_id]['progress_task'].cancel()
        client:VC = voice_data[guild_id]["client"]

        if client.is_connected():
            await client.disconnect(force=True)
            await voice_data[guild_id]["music_channel"].send("已停止並斷開連接")
        asyncio.sleep(1)
        if guild_id in voice_data:
            del voice_data[guild_id]

    async def play_next(guild_id):
        try:
            data = db_handler.get(query={"_id":guild_id})[0]
            embed_msg:discord.Message = voice_data[guild_id]["state_embed_message"]
            embed = embed_msg.embeds.pop()
            embed.description = '播放完畢'
            await embed_msg.edit(embed=embed, view=None)
            queue = data.get('queue',None)
            db_handler.append(
                query={"_id":guild_id},
                field="played",
                value=data.get("current_playing")
            )
            if len(queue) > 0 :
                await Functions._play(guild_id)
            else:
                await Functions._stop(guild_id)
        except Exception as e:
            logger.error(f"play_next error: {e}")
            await Functions._stop( guild_id)
            await voice_data[guild_id]["music_channel"].send("播放下一首時出現問題", delete_after=10)

    async def search(itat:Itat, request, region='youtube'):
        try:
            guild_id = itat.guild_id
            await itat.followup.send(f"正在搜尋: `{request}`...", ephemeral=True)

            match region:
                case 'youtube':
                    results = await Youtube.get_youtube_search_results(request, max_results=10)

            if len(results) == 0:
                await itat.followup.send("找不到任何結果。", ephemeral=True)
                return
            
            video_opt = [
                discord.SelectOption(
                    label=f"{title or 'Unknown title'}"[:100],
                    description=f"by {author or 'Unknown Artist'}"[:100],
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
                    song_url = s_itat.data['values'][0]
                    await original_message.edit(content="處理中...", view=None)
                    song_data = await Youtube.get_data(song_url)
                    
                    db_handler.append(
                        query={"_id":guild_id},
                        field="queue",
                        value=song_data
                    )

                    if "client" not in voice_data[guild_id] or not voice_data[guild_id]["client"].is_connected():
                        await Functions._play(guild_id)

                except Exception as e:
                    print(f"search_callback error: {e}")

            search_menu.callback = search_menu_callback

        except Exception as e:
            logger.error(f"search error: {e}")
            await itat.followup.send("搜尋時發生錯誤，請使用有效連結或再試一次。", ephemeral=True)

    async def playback_status_updater(guild_id):
        try:
            while guild_id in voice_data:
                if "client" not in voice_data[guild_id]:break

                client:VC = voice_data[guild_id]["client"]
                data = db_handler.get(query={"_id":guild_id})[0]
                human_members = [member for member in client.channel.members if not member.bot]

                if len(human_members) == 0:
                    logger.info(f"No human users left in voice channel for guild {guild_id}. Stopping playback.")
                    await Functions._stop(guild_id)
                    break

                embed_msg:discord.Message = voice_data[guild_id].get("state_embed_message")

                if embed_msg:
                    embed = embed_msg.embeds[0]
                    new_progress_bar = music_utils.generate_progress_bar(guild_id)
                    if embed.description != new_progress_bar:
                        embed.description = new_progress_bar
                        control_view = ControlView(guild_id)
                        try:
                            await embed_msg.edit(embed=embed, view=control_view)
                        except discord.NotFound:
                            break
                
                await asyncio.sleep(1)

                guild_data = voice_data.get(guild_id)
                if guild_data:
                    embed_msg = guild_data.get("embed_msg")
                    if embed_msg:
                        embed = embed_msg.embeds[0]
                        embed.description = "播放完畢"
                        await embed_msg.edit(embed=embed, view=None)

        except Exception as e:
            logger.error(f"update_progress_bar encountered a fatal error: {e}")