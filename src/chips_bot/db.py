from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from chips_bot.models import Base


@dataclass(frozen=True)
class Database:
    engine: Engine
    session_factory: sessionmaker[Session]


def create_database(database_url: str) -> Database:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args, future=True)
    return Database(engine=engine, session_factory=sessionmaker(bind=engine, expire_on_commit=False))


def init_db(database: Database) -> None:
    Base.metadata.create_all(database.engine)
