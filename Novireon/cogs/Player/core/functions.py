import asyncio
import discord
import logging
import random
import time
import os

from discord.ui import View
from discord import Interaction as Itat
from discord import VoiceClient as VC
from pymongo import MongoClient

from mongo_crud import MongoCRUD
from Novireon.cogs.Player.monster_siren import Monster_siren
from Novireon.cogs.Player.spotify import Spotify
from Novireon.cogs.Player.youtube import Youtube
from Novireon.cogs.Player.core import utils
from Novireon.cogs.Player.data import voice_data
from Novireon.cogs.Player.core.view.control_views import ControlView
from Novireon.src.util.config import get_config
from Novireon.cogs.Player.core.request_manager import RequestManager

logger = logging.getLogger("player.functions")
logger.setLevel(logging.INFO)
player_config = get_config("Player")

ffmpeg_options = {
    "before_options": (
        "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
        "-probesize 10M "
        "-analyzeduration 10M "
        "-fflags +genpts+igndts "
    ),
    "options": ("-vn " "-threads auto " '-af "volume=1.0" ' "-b:a 128k " "-application audio " "-frame_duration 20 "),
}

mongo_uri = os.getenv("MONGO_URI")
mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=15000)

db_handler = MongoCRUD(
    client=mongo_client,
    db_name="Norvireon_bot_db",
    collection_name="Player_data",
    logger=logger,
)


class Functions:

    @staticmethod
    async def _pause(guild_id):
        await RequestManager.request_op(guild_id, "pause", Functions._pause_op, guild_id)

    @staticmethod
    async def _pause_op(guild_id):
        try:
            client: VC = voice_data[guild_id].get("client")
            data = db_handler.get(query={"_id": guild_id})[0]
            player_channel: discord.TextChannel = voice_data[guild_id]["player_channel"]
            if client and data.get("is_playing"):
                client.pause()
                db_handler.update_many(
                    query={"_id": guild_id},
                    new_values={"is_playing": False, "pause_time": time.time()},
                )
                await player_channel.send("音樂已暫停", delete_after=5)
        except Exception as e:
            logger.error(f"pause command error: {e}")

    @staticmethod
    async def pre_play(itat: Itat, request):
        guild_id = itat.guild_id
        RequestManager.ensure_worker(guild_id)

        voice_data[guild_id]["player_channel"] = itat.channel
        voice_data[guild_id]["itat"] = itat

        match utils.get_source_name(request):
            case "youtube":
                try:
                    data = await Youtube.get_data_from_single(request)
                except ValueError as e:
                    await itat.followup.send(str(e), ephemeral=True)
                    return
            case "monster_siren":
                data = await Monster_siren.get_song_data(request)
            case "spotify":
                try:
                    request: str = Spotify.get_spotify_song_data(request)
                    results = await Youtube.get_youtube_search_results(request, 5)
                    for result in results:
                        if request.split(" ")[0] in result["title"]:
                            url = result["url"]
                            break
                    data = await Youtube.get_data_from_single(url)
                except:
                    pass
            case "direct_audio":
                try:
                    duration = await utils.get_web_audio_duration(request)
                    avatar = itat.user.display_avatar.url if itat.user.display_avatar else None
                    data = {
                        "author": "Unknown Artist",
                        "title": "Unknown Title",
                        "song_url": request,
                        "duration": duration,
                        "thumbnail": avatar,
                    }
                except:
                    pass
            case "":
                try:
                    data = await Functions.search(itat, request)
                except:
                    pass
            case _:
                pass

        user = itat.user.nick if itat.user.nick else itat.user.name
        if data is None:
            await itat.followup.send("找不到相關的音樂，請嘗試其他關鍵字或網址", ephemeral=True)
            return
        else:
            data.update({"requester": user})
            await RequestManager.request_op(
                guild_id, "play_resolved", Functions._play_resolved_op, guild_id, itat, data
            )

    @staticmethod
    async def _play_resolved_op(guild_id, itat: Itat, data):
        db_handler.append(query={"_id": guild_id}, field="queue", value=data)

        if ("client" not in voice_data[guild_id]) or (not voice_data[guild_id]["client"].is_connected()):
            await itat.followup.send("正在處理播放請求", ephemeral=True)
            await Functions._play(guild_id)
        else:
            embed = utils.create_queue_embed(data)
            await itat.channel.send(embed=embed)

    @staticmethod
    async def pre_play_playlist(itat: Itat, request, max_results, if_shuffle):
        if max_results < 1:
            max_results = 1
        elif max_results > player_config["limits.max_song_count_add_via_playlist"]:
            max_results = player_config["limits.max_song_count_add_via_playlist"]

        await itat.response.send_message("處理中", ephemeral=True)

        guild_id = itat.guild_id
        RequestManager.ensure_worker(guild_id)

        voice_data[guild_id]["player_channel"] = itat.channel
        voice_data[guild_id]["itat"] = itat

        metadatas = await Youtube.get_playlist_metadata(request)
        if metadatas is None:
            await itat.followup.send("找不到相關的播放列表，請嘗試其他關鍵字或網址", ephemeral=True)
            return

        max_songs_count = min(
            max_results,
            len(metadatas),
            player_config["limits.max_song_count_add_via_playlist"],
        )
        if if_shuffle:
            selected_songs = random.sample(metadatas, max_songs_count)
        else:
            selected_songs = metadatas[:max_songs_count]

        user = itat.user.nick if itat.user.nick else itat.user.name
        for song in selected_songs:
            if guild_id in voice_data and voice_data[guild_id].get("is_stopped"):
                break
            try:
                data = await Youtube.get_data_from_single(song["webpage_url"])
                if guild_id not in voice_data or voice_data[guild_id].get("is_stopped"):
                    break
                data.update({"requester": user})
                db_handler.append(query={"_id": guild_id}, field="queue", value=data)
                embed = utils.create_queue_embed(data)
                await itat.channel.send(embed=embed)
                await asyncio.sleep(1)
            except Exception as e:
                await itat.channel.send("加入播放列表時發生錯誤，部分歌曲可能未加入佇列。")
                logger.error(f"Error adding song from playlist: {e}")
                continue

        if guild_id in voice_data and not voice_data[guild_id].get("is_stopped"):
            await RequestManager.request_op(guild_id, "start_play", Functions._start_play_op, guild_id, itat)

    @staticmethod
    async def _start_play_op(guild_id, itat: Itat):
        if ("client" not in voice_data[guild_id]) or (not voice_data[guild_id]["client"].is_connected()):
            await itat.followup.send("正在處理播放請求", ephemeral=True)
            await Functions._play(guild_id)

    @staticmethod
    async def _play(guild_id):
        try:
            loop = asyncio.get_event_loop()
            player_channel: discord.TextChannel = voice_data[guild_id]["player_channel"]

            def after_play(error):
                if error:
                    logger.info(f"Player error: {error}")
                if guild_id in voice_data and not voice_data[guild_id].get("is_stopped"):
                    future = asyncio.run_coroutine_threadsafe(
                        RequestManager.request_op(guild_id, "play_next", Functions._play_next_op, guild_id), loop
                    )
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Error in after_play callback: {e}")

            next_song_data = db_handler.pop(query={"_id": guild_id}, field="queue")

            try:
                itat: Itat = voice_data[guild_id]["itat"]
                if "client" not in voice_data[guild_id] or not voice_data[guild_id]["client"].is_connected():
                    try:
                        voice_client: VC = await itat.user.voice.channel.connect(reconnect=False)
                    except asyncio.TimeoutError:
                        await itat.followup.send("無法連接至語音頻道", ephemeral=True)
                    voice_data[guild_id]["client"] = voice_client
                else:
                    voice_client = voice_data[guild_id]["client"]

                await player_channel.send("正在載入...", delete_after=5)
                try:
                    source = discord.FFmpegOpusAudio(next_song_data["song_url"], **ffmpeg_options)
                except Exception as e:
                    logger.error(f"FFmpegOpusAudio error: {e}")
                voice_client.play(source, after=after_play)

            except Exception as e:
                logger.error(f"Error during playback: {e}")
                await itat.followup.send("無法播放，請檢查連結或聯絡開發者", ephemeral=True)

            db_handler.update_one(
                query={"_id": guild_id},
                new_values={
                    "start_time": time.time(),
                    "pause_time": None,
                    "total_paused_duration": None,
                    "is_playing": True,
                },
                upsert=True,
            )

            embed = discord.Embed(
                title=next_song_data["title"],
                description="播放中...",
                color=player_config["colors.playing"],
            )
            thumbnail = next_song_data.get("thumbnail", None)
            if thumbnail:
                embed.set_thumbnail(url=thumbnail)
            requester = f'{next_song_data.get("requester", False)}'
            if requester:
                embed.add_field(name="\u200b", value=f"由{requester}加入")
            control_view = ControlView(guild_id)
            embed_msg = await player_channel.send(view=control_view, embed=embed)
            voice_data[guild_id]["state_embed_message"] = embed_msg

            db_handler.update_one(
                query={"_id": guild_id},
                new_values={"current_playing": next_song_data},
                upsert=True,
            )

            if "playback_state_updater" in voice_data[guild_id]:
                try:
                    voice_data[guild_id]["playback_state_updater"].cancel()
                except Exception:
                    pass
            voice_data[guild_id]["playback_state_updater"] = asyncio.create_task(
                Functions.playback_state_updater(guild_id)
            )
        except Exception as e:
            if guild_id in voice_data and "player_channel" in voice_data[guild_id]:
                await voice_data[guild_id]["player_channel"].send("無法播放，請使用連結或再試一次", delete_after=10)
            logger.error(f"_play error: {e}")

    @staticmethod
    async def _resume(guild_id):
        await RequestManager.request_op(guild_id, "resume", Functions._resume_op, guild_id)

    @staticmethod
    async def _resume_op(guild_id):
        try:
            client: VC = voice_data[guild_id].get("client")
            data = db_handler.get(query={"_id": guild_id})[0]
            player_channel: discord.TextChannel = voice_data[guild_id]["player_channel"]
            if client and not data.get("is_playing"):
                client.resume()
                paused_for = time.time() - data["pause_time"]
                paused_time = data.get("total_paused_duration")
                if paused_time is None:
                    paused_time = 0
                db_handler.update_many(
                    query={"_id": guild_id},
                    new_values={
                        "total_paused_duration": paused_for + paused_time,
                        "is_playing": True,
                    },
                )
                await player_channel.send("音樂已恢復播放", delete_after=5)
        except Exception as e:
            logger.error(f"resume command error: {e}")

    @staticmethod
    async def _skip(guild_id):
        await RequestManager.request_op(guild_id, "skip", Functions._skip_op, guild_id)

    @staticmethod
    async def _skip_op(guild_id):
        try:
            client: VC = voice_data[guild_id].get("client")
            data = db_handler.get(query={"_id": guild_id})[0]
            player_channel = voice_data[guild_id].get("player_channel")
            if client and data.get("is_playing"):
                client.stop()
            else:
                if player_channel:
                    await player_channel.send("沒有正在播放的音樂", delete_after=5)
        except Exception as e:
            player_channel = voice_data[guild_id].get("player_channel")
            if player_channel:
                await player_channel.send("播放下一首時出現問題", delete_after=10)
            await Functions._stop_op(guild_id)
            logger.error(f"skip command error: {e}")

    @staticmethod
    async def _stop(guild_id):
        await RequestManager.request_op(guild_id, "stop", Functions._stop_op, guild_id)

    @staticmethod
    async def _stop_op(guild_id):
        try:
            if guild_id not in voice_data:
                return

            voice_data[guild_id]["is_stopped"] = True

            if "playback_state_updater" in voice_data[guild_id]:
                try:
                    voice_data[guild_id]["playback_state_updater"].cancel()
                except Exception:
                    pass

            if "client" in voice_data[guild_id]:
                client: VC = voice_data[guild_id]["client"]
                if client.is_connected():
                    utils.return_to_default_player_settings(guild_id)
                    await client.disconnect(force=True)
                    await asyncio.sleep(1)

            if "player_channel" in voice_data[guild_id]:
                try:
                    await voice_data[guild_id]["player_channel"].send("已停止並斷開連接")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"stop error: {e}")

    @staticmethod
    async def play_next(guild_id):
        await RequestManager.request_op(guild_id, "play_next", Functions._play_next_op, guild_id)

    @staticmethod
    async def _play_next_op(guild_id):
        try:
            data = db_handler.get(query={"_id": guild_id})[0]
            current_playing = data.get("current_playing", None)
            embed_msg: discord.Message = voice_data[guild_id].get("state_embed_message")
            if embed_msg:
                try:
                    embed = embed_msg.embeds.pop()
                    embed.description = "播放完畢"
                    await embed_msg.edit(embed=embed, view=None)
                except Exception:
                    pass
            if current_playing is None:
                return
            queue = data.get("queue", None)
            try:
                if not current_playing.get("is_live", False):
                    current_playing_history = {
                        "author": current_playing.get("author"),
                        "title": current_playing.get("title"),
                    }
                    db_handler.append(
                        query={"_id": guild_id},
                        field="played",
                        value=current_playing_history,
                    )
            except:
                pass
            if queue and len(queue) > 0:
                await Functions._play(guild_id)
            else:
                await Functions._stop_op(guild_id)
        except Exception as e:
            logger.error(f"play_next error: {e}")
            await Functions._stop_op(guild_id)
            player_channel = voice_data[guild_id].get("player_channel")
            if player_channel:
                try:
                    await player_channel.send("播放下一首時出現問題", delete_after=10)
                except Exception:
                    pass

    @staticmethod
    async def search(itat: Itat, request, region="youtube"):
        try:
            await itat.followup.send(f"正在搜尋: `{request}`...", ephemeral=True)

            match region:
                case "youtube":
                    results = await Youtube.get_youtube_search_results(request, max_results=10)

            if len(results) == 0:
                await itat.followup.send("找不到任何結果。", ephemeral=True)
                return

            video_opt = [
                discord.SelectOption(
                    label=f"{title or 'Unknown title'}"[:100],
                    description=f"by {author or 'Unknown Artist'}"[:100],
                    value=url,
                )
                for url, title, author in [
                    (
                        result["url"],
                        result["title"],
                        result["author"],
                    )
                    for result in results
                ]
            ]
            search_menu = discord.ui.Select(placeholder="選擇一首歌", options=video_opt, min_values=1, max_values=1)
            view = View(timeout=30)
            view.add_item(search_menu)
            future = asyncio.Future()

            async def on_timeout():
                if not future.done():
                    future.set_result(None)
                search_menu.disabled = True
                await original_message.edit(content="選擇已超時，請重新搜尋。", view=None)

            view.on_timeout = on_timeout

            async def search_menu_callback(s_itat: Itat):
                try:
                    search_menu.disabled = True
                    song_url = s_itat.data["values"][0]
                    await original_message.edit(content="處理中...", view=None)

                    match region:
                        case "youtube":
                            song_data = await Youtube.get_data_from_single(song_url)
                    if not future.done():
                        future.set_result(song_data)

                except Exception as e:
                    logger.error(f"search_callback error: {e}")

            search_menu.callback = search_menu_callback

            original_message = await itat.followup.send(content="請從下方選擇一個結果", view=view, ephemeral=True)
            selected_song_data = await future
            return selected_song_data

        except Exception as e:
            logger.error(f"search error: {e}")
            await itat.followup.send("搜尋時發生錯誤，請使用有效連結或再試一次。", ephemeral=True)

    @staticmethod
    async def playback_state_updater(guild_id):
        try:
            while guild_id in voice_data:
                if "client" not in voice_data[guild_id]:
                    break

                client: VC = voice_data[guild_id]["client"]
                human_members = [member for member in client.channel.members if not member.bot]

                if len(human_members) == 0:
                    logger.info(f"No users left in voice channel for guild {guild_id}. Stopping playback.")
                    await Functions._stop(guild_id)
                    break

                embed_msg: discord.Message = voice_data[guild_id].get("state_embed_message")

                if embed_msg:
                    if len(embed_msg.embeds) == 0:
                        logger.warning(f"Embed message has no embeds for guild {guild_id}.")
                        break
                    embed = embed_msg.embeds[0]
                    new_progress_bar = utils.generate_progress_bar(guild_id)
                    if embed.description != new_progress_bar:
                        embed.description = new_progress_bar
                        control_view = ControlView(guild_id)
                        try:
                            await embed_msg.edit(embed=embed, view=control_view)
                        except discord.NotFound:
                            break

                await asyncio.sleep(player_config["playback.state.update_interval"])

                guild_data = voice_data.get(guild_id)
                if guild_data:
                    embed_msg = guild_data.get("embed_msg")
                    if embed_msg:
                        try:
                            embed = embed_msg.embeds[0]
                            embed.description = "播放完畢"
                            await embed_msg.edit(embed=embed, view=None)
                        except Exception:
                            pass

        except Exception as e:
            logger.error(f"update_progress_bar encountered a fatal error: {e}")
