import logging
import os

from dotenv import load_dotenv

from Novireon.bot import bot
from logging_config import setup_logging

if __name__ == "__main__":
    load_dotenv()
    setup_logging()
    TOKEN = os.getenv("DISCORD")
    if TOKEN:
        logging.info("starting bot")
        bot.run(TOKEN, log_level=logging.WARN)
