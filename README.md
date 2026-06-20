# Poker Bot

A Telegram group bot for settling poker chip games with host commission, minimized payment transactions, game history, and commission stats.

## Features

- Host starts one active game per Telegram group with `/newgame`.
- Players submit or update their own entries with `/submit` or `/join`.
- Settlement logic uses `Decimal` and integer cents, never raw floats.
- Winners pay a configurable host commission percentage.
- Host can be a player, including a winning player, and accounting remains balanced.
- Completed games, transactions, and host commission stats are persisted in SQLite.
- Core calculation logic is pure Python and covered by pytest.

## Local Setup

Requires Python 3.10+.

Run these commands from the repository root.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

If PowerShell blocks activation scripts on your machine, run this once for the current shell and then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Edit `.env` and set your bot token. `DATABASE_URL` can stay as the local SQLite default unless you want a different database file.

```text
TELEGRAM_BOT_TOKEN=your_bot_token
DATABASE_URL=sqlite:///chips_bot.sqlite3
```

The editable install is important because this project uses a `src/` layout. After `python -m pip install -e ".[dev]"`, Python can import the package as `chips_bot` from anywhere inside the virtual environment.

## Run

Start the Telegram bot locally:

```powershell
python -m chips_bot.main
```

Do not run `python -m src.chips_bot.main`; that bypasses the installed package name and can fail with `ModuleNotFoundError: No module named 'chips_bot'`.

If the bot exits with `RuntimeError: TELEGRAM_BOT_TOKEN is required`, check that `.env` is in the repository root and is not empty. It should contain a non-placeholder token:

```text
TELEGRAM_BOT_TOKEN=1234567890:your_real_telegram_bot_token
DATABASE_URL=sqlite:///chips_bot.sqlite3
```

You can verify that PowerShell sees the file without printing your token:

```powershell
Get-ChildItem -Force .env | Select-Object Name,Length
```

## Test

Run the full test suite:

```powershell
pytest
```

Or, to make sure you are using the virtual environment's Python explicitly:

```powershell
python -m pytest
```

Optional syntax/import check:

```powershell
python -m compileall src tests
```

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
# edit .env and set TELEGRAM_BOT_TOKEN
python -m pytest
python -m chips_bot.main
```

## Bot Commands

- `/newgame` - start a new game as host
- `/submit` or `/join` - submit or update your entry
- `/status` - view current submissions
- `/calculate` - finalize the active game, host only
- `/history` - show recent completed games
- `/stats` - show host commission totals
- `/cancelgame` - cancel the active game, host only
- `/help` - show help

## Project Layout

```text
src/chips_bot/
	settlement.py          pure calculation logic
	models.py              SQLAlchemy models
	db.py                  database setup
	formatters.py          Telegram-safe output formatting
	repositories/          persistence access layer
	handlers/              Telegram command and conversation handlers
tests/                   settlement, formatter, and repository tests
```
