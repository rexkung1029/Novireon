import asyncio
import logging
from Novireon.cogs.Player.data import voice_data
from Novireon.cogs.Player.core import utils

logger = logging.getLogger("player.queue_manager")
logger.setLevel(logging.INFO)


class RequestManager:
    @staticmethod
    def ensure_worker(guild_id):
        if guild_id not in voice_data:
            voice_data[guild_id] = {}
            utils.return_to_default_player_settings(guild_id)

        if "request" not in voice_data[guild_id]:
            voice_data[guild_id]["request"] = asyncio.Queue()

        if "worker_task" not in voice_data[guild_id] or voice_data[guild_id]["worker_task"].done():
            voice_data[guild_id]["worker_task"] = asyncio.create_task(RequestManager.player_worker(guild_id))

    @staticmethod
    async def request_op(guild_id, op_type, action, *args, **kwargs):
        RequestManager.ensure_worker(guild_id)

        if voice_data[guild_id].get("is_stopped") and op_type != "stop":
            return None

        future = asyncio.Future()
        op = {"type": op_type, "action": action, "args": args, "kwargs": kwargs, "future": future}
        await voice_data[guild_id]["request"].put(op)
        return await future

    @staticmethod
    async def player_worker(guild_id):
        queue = voice_data[guild_id]["request"]
        while True:
            try:
                op = await queue.get()

                if guild_id in voice_data and voice_data[guild_id].get("is_stopped") and op["type"] != "stop":
                    if "future" in op and not op["future"].done():
                        op["future"].set_result(None)
                    queue.task_done()
                    continue

                try:
                    action = op["action"]
                    res = await action(*op["args"], **op["kwargs"])
                    if "future" in op and not op["future"].done():
                        op["future"].set_result(res)
                except Exception as action_exc:
                    logger.error(f"Action failed in player_worker for guild {guild_id}: {action_exc}")
                    if "future" in op and not op["future"].done():
                        op["future"].set_exception(action_exc)

                if op["type"] == "stop" or (guild_id in voice_data and voice_data[guild_id].get("is_stopped")):
                    if guild_id in voice_data:
                        del voice_data[guild_id]
                    queue.task_done()
                    break

                queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in player_worker for guild {guild_id}: {e}")
                if "future" in op and not op["future"].done():
                    op["future"].set_exception(e)
                queue.task_done()
