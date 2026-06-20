from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes


HELP_TEXT = """Poker Chips Settlement Bot

Commands:
/newgame - start a new game as host
/submit or /join - submit or update your entry
/status - view current submissions
/calculate - finalize the active game, host only
/history - show recent completed games
/stats - show host commission totals
/cancelgame - cancel the active game, host only
/help - show this help
"""


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is not None:
        await update.effective_message.reply_text(HELP_TEXT)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await help_command(update, context)
