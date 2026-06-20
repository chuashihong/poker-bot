from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    host_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    host_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    chip_value_sgd: Mapped[str] = mapped_column(Text, nullable=False)
    host_commission_percent: Mapped[str] = mapped_column(Text, nullable=False)
    buy_in_mode: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(Text)

    entries: Mapped[list[PlayerEntryModel]] = relationship(back_populates="game", cascade="all, delete-orphan")
    results: Mapped[list[GameResult]] = relationship(back_populates="game", cascade="all, delete-orphan")
    transactions: Mapped[list[SettlementTransaction]] = relationship(back_populates="game", cascade="all, delete-orphan")


class PlayerEntryModel(Base):
    __tablename__ = "player_entries"
    __table_args__ = (UniqueConstraint("game_id", "telegram_user_id", name="uq_entry_game_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    remaining_chips: Mapped[str] = mapped_column(Text, nullable=False)
    buy_in_original: Mapped[str] = mapped_column(Text, nullable=False)
    buy_in_sgd: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    game: Mapped[Game] = relationship(back_populates="entries")


class GameResult(Base):
    __tablename__ = "game_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    net_before_commission_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_paid_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    final_net_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    game: Mapped[Game] = relationship(back_populates="results")


class SettlementTransaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    from_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    to_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    game: Mapped[Game] = relationship(back_populates="transactions")


class HostCommissionStat(Base):
    __tablename__ = "host_commission_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    host_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    host_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    total_commission_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
