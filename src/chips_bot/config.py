from dataclasses import dataclass
from os import getenv

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    database_url: str
    mini_app_url: str | None
    mini_app_host: str
    mini_app_port: int


def load_config() -> Config:
    token = getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    mini_app_url = getenv("MINI_APP_URL")
    return Config(
        telegram_bot_token=token,
        database_url=getenv("DATABASE_URL", "sqlite:///chips_bot.sqlite3"),
        mini_app_url=mini_app_url.rstrip("/") if mini_app_url else None,
        mini_app_host=getenv("MINI_APP_HOST", "127.0.0.1"),
        mini_app_port=int(getenv("MINI_APP_PORT", getenv("PORT", "8080"))),
    )
