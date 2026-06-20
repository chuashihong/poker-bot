from dataclasses import dataclass
from os import getenv

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    database_url: str


def load_config() -> Config:
    token = getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    return Config(
        telegram_bot_token=token,
        database_url=getenv("DATABASE_URL", "sqlite:///chips_bot.sqlite3"),
    )
