from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler
from uvicorn import Config as UvicornConfig, Server

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
from chips_bot.mini_app import create_mini_app, url_origin


async def start_mini_app_server(app: Application) -> None:
    config = app.bot_data["config"]
    if not config.mini_app_url:
        return

    mini_app = create_mini_app(
        database=app.bot_data["database"],
        bot=app.bot,
        bot_token=config.telegram_bot_token,
        pending_setups=app.bot_data["pending_new_game_setups"],
        allowed_origins=[url_origin(config.mini_app_url)],
    )
    server = Server(UvicornConfig(mini_app, host=config.mini_app_host, port=config.mini_app_port, log_level="info"))
    app.bot_data["mini_app_server"] = server
    app.create_task(server.serve(), name="mini-app-server")


async def stop_mini_app_server(app: Application) -> None:
    server = app.bot_data.get("mini_app_server")
    if server is not None:
        server.should_exit = True


def build_application() -> Application:
    config = load_config()
    database = create_database(config.database_url)
    init_db(database)

    builder = Application.builder().token(config.telegram_bot_token)
    if config.mini_app_url:
        builder = builder.post_init(start_mini_app_server).post_shutdown(stop_mini_app_server)
    app = builder.build()
    app.bot_data["config"] = config
    app.bot_data["database"] = database
    app.bot_data["pending_new_game_setups"] = {}

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
