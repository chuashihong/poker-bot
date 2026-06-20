from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from chips_bot.config import load_config
from chips_bot.db import create_database, init_db
from chips_bot.handlers.calculate import calculate_command
from chips_bot.handlers.cancel_game import cancel_game_command
from chips_bot.handlers.help import help_command, start_command
from chips_bot.handlers.history import history_command
from chips_bot.handlers.new_game import new_game_handler
from chips_bot.handlers.stats import stats_command
from chips_bot.handlers.status import status_command
from chips_bot.handlers.submit import submit_handler


def build_application() -> Application:
    config = load_config()
    database = create_database(config.database_url)
    init_db(database)

    app = Application.builder().token(config.telegram_bot_token).build()
    app.bot_data["database"] = database

    app.add_handler(new_game_handler())
    app.add_handler(submit_handler())
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("calculate", calculate_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("cancelgame", cancel_game_command))
    app.add_handler(CallbackQueryHandler(status_command, pattern="^view_status$"))
    app.add_handler(CallbackQueryHandler(calculate_command, pattern="^calculate_game$"))
    return app


def main() -> None:
    app = build_application()
    app.run_polling()


if __name__ == "__main__":
    main()
