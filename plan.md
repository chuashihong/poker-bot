# Telegram Poker Chips Settlement Bot — Codex Implementation Plan

## 1. Goal

Build a Python Telegram bot for a Telegram group that helps a host settle poker / chip-based games.

Players enter:

- Display name
- Chips remaining at the end of the game
- Total buy-in amount, in chips or SGD depending on chosen mode

The host starts calculation after everyone has submitted. The bot returns:

- Each player’s net win/loss
- Host commission from winners, based on a configurable percentage of winnings
- Final settlement transactions: who pays who, and how much
- Game history
- Total commission ever given to host across all games

The bot should be designed for group usage, where many players can submit their own records, but only the host can finalize the game.

---

## 2. Recommended Tech Stack

Use:

- Python 3.11+
- `python-telegram-bot` v22+
- SQLite for local persistence
- SQLAlchemy 2.x or plain `sqlite3`; prefer SQLAlchemy if project is expected to grow
- `python-dotenv` for local config
- `pytest` for settlement logic tests

Reasoning:

- `python-telegram-bot` v22+ is async-first and supports `Application`, `CommandHandler`, `CallbackQueryHandler`, and `ConversationHandler`.
- Telegram inline keyboards are a good fit for a simple in-group UI.
- SQLite is enough for a personal/group bot and keeps deployment simple.

Useful official references:

- `python-telegram-bot` docs: https://docs.python-telegram-bot.org/
- Telegram Bot API docs: https://core.telegram.org/bots/api

---

## 3. Core Product Flow

### 3.1 Group setup

The bot is added to a Telegram group.

Commands:

```text
/newgame
/join
/submit
/status
/calculate
/history
/stats
/cancelgame
/help
```

### 3.2 Start a game

Host runs:

```text
/newgame
```

Bot asks host for:

1. Chip value in SGD, default `0.1`
2. Host commission percentage from winners, default `0`
3. Whether buy-in input is in `chips` or `sgd`

Example:

```text
Game created by Chua.
Chip value: SGD 0.10
Host commission: 2% of positive winnings
Buy-in mode: SGD

Players can now press Join / Submit Entry.
```

### 3.3 Player submission UI

Each player can use:

```text
/submit
```

Bot starts a private or group conversation. Prefer private conversation if possible, but group conversation is acceptable for MVP.

Input flow:

```text
Enter your display name:
Enter your remaining chips:
Enter your total buy-in:
Confirm?
```

Example player entry:

```text
Name: Samson
Remaining chips: 666
Buy-in: 200 SGD
```

If buy-in mode is `SGD`, convert buy-in to chips internally using:

```python
buy_in_chips = buy_in_sgd / chip_value_sgd
```

If buy-in mode is `chips`, use the number directly.

Store both original input and normalized values.

### 3.4 Game status

Anyone can run:

```text
/status
```

Bot returns current entries:

```text
Current game #12
Host: Chua
Chip value: SGD 0.10
Host commission: 2%

Submitted players:
1. Samson — 666 chips, buy-in SGD 200
2. Ziyi — 353 chips, buy-in SGD 200
3. Chua — 575 chips, buy-in SGD 600
```

### 3.5 Final calculation

Only host can run:

```text
/calculate
```

Bot validates:

- Active game exists
- Caller is host
- At least 2 players submitted
- No invalid negative values
- Sum of net results is mathematically consistent after commission

Bot outputs:

```text
Final Result — Game #12

Each chip = SGD 0.10
Host commission = 2% of positive winnings
Host = Chua

Net before commission:
- es: +36.20
- Gzg: +13.50
- Gzs: -20.00
- samson: -40.00
- Chua: -2.50

Host commission collected:
- es pays Chua commission SGD 0.72
- Gzg pays Chua commission SGD 0.27

Total host commission: SGD 0.99

Final settlement:
- samson pays es SGD 35.48
- samson pays ziyi SGD 4.52
- Gzs pays ziyi SGD 10.47
- Chua pays jervin SGD 0.73
```

After calculation, mark game as `completed` and save all results to history.

---

## 4. Settlement Logic

### 4.1 Definitions

For each player:

```python
ending_value_sgd = remaining_chips * chip_value_sgd
buy_in_sgd = normalized_buy_in_sgd
net_before_commission = ending_value_sgd - buy_in_sgd
```

Positive net means winner.
Negative net means loser.
Zero means break-even.

### 4.2 Host commission rule

If host commission is `p%`, every winner pays:

```python
commission = max(net_before_commission, 0) * (p / 100)
```

Then:

```python
winner_final_net = net_before_commission - commission
host_final_net = host_net_before_commission + sum(all_commissions)
```

Important:

- The host can also be a winner.
- If the host is a winner, the host also pays commission into the host pool, but because the host receives the whole pool, this nets out naturally if implemented consistently.
- Simpler implementation: calculate commission for every winner including host, subtract it from the winner, then add total commission to host.

This makes the accounting balanced.

### 4.3 Rounding rule

Use integer cents internally to avoid floating point errors.

Example:

```python
from decimal import Decimal, ROUND_HALF_UP

amount = Decimal("36.20")
cents = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
```

Recommended internal representation:

```python
net_cents: int
commission_cents: int
final_net_cents: int
```

Only format to SGD at display time.

### 4.4 Settlement minimization algorithm

Goal: produce a small list of transactions that settles all final nets.

Inputs:

```python
final_nets = {
    "es": 3548,
    "Gzg": 1323,
    "Gzs": -2000,
    "samson": -4000,
    "Chua": -111,
}
```

Values are cents.

Algorithm:

1. Split players into creditors and debtors.
2. Creditors have positive final net.
3. Debtors have negative final net.
4. Sort both lists descending by absolute amount.
5. Use two pointers:
   - debtor pays creditor the minimum of remaining debt and remaining credit
   - reduce both balances
   - advance pointer when one side reaches zero

Pseudo-code:

```python
def settle(final_nets: dict[str, int]) -> list[Transaction]:
    creditors = [Balance(name, amount) for name, amount in final_nets.items() if amount > 0]
    debtors = [Balance(name, -amount) for name, amount in final_nets.items() if amount < 0]

    creditors.sort(key=lambda x: x.amount_cents, reverse=True)
    debtors.sort(key=lambda x: x.amount_cents, reverse=True)

    txs = []
    i = 0
    j = 0

    while i < len(debtors) and j < len(creditors):
        pay_cents = min(debtors[i].amount_cents, creditors[j].amount_cents)

        txs.append(Transaction(
            from_player=debtors[i].name,
            to_player=creditors[j].name,
            amount_cents=pay_cents,
        ))

        debtors[i].amount_cents -= pay_cents
        creditors[j].amount_cents -= pay_cents

        if debtors[i].amount_cents == 0:
            i += 1
        if creditors[j].amount_cents == 0:
            j += 1

    return txs
```

### 4.5 Full calculation function shape

Codex should implement something close to this:

```python
@dataclass
class PlayerEntry:
    telegram_user_id: int
    name: str
    remaining_chips: Decimal
    buy_in_sgd: Decimal

@dataclass
class PlayerResult:
    name: str
    net_before_commission_cents: int
    commission_paid_cents: int
    final_net_cents: int

@dataclass
class Transaction:
    from_player: str
    to_player: str
    amount_cents: int

@dataclass
class SettlementResult:
    player_results: list[PlayerResult]
    transactions: list[Transaction]
    total_host_commission_cents: int


def calculate_settlement(
    entries: list[PlayerEntry],
    chip_value_sgd: Decimal,
    host_telegram_user_id: int,
    host_commission_percent: Decimal,
) -> SettlementResult:
    # 1. Calculate net before commission for each player.
    # 2. Calculate commission for winners.
    # 3. Subtract commission from winners.
    # 4. Add total commission to host.
    # 5. Validate sum(final_net_cents) == 0.
    # 6. Generate settlement transactions.
    pass
```

---

## 5. Database Design

Use SQLite.

### 5.1 `games`

```sql
CREATE TABLE games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    host_user_id INTEGER NOT NULL,
    host_display_name TEXT NOT NULL,
    chip_value_sgd TEXT NOT NULL,
    host_commission_percent TEXT NOT NULL,
    buy_in_mode TEXT NOT NULL CHECK (buy_in_mode IN ('SGD', 'CHIPS')),
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'COMPLETED', 'CANCELLED')),
    created_at TEXT NOT NULL,
    completed_at TEXT
);
```

### 5.2 `player_entries`

```sql
CREATE TABLE player_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    telegram_user_id INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    remaining_chips TEXT NOT NULL,
    buy_in_original TEXT NOT NULL,
    buy_in_sgd TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(game_id, telegram_user_id),
    FOREIGN KEY(game_id) REFERENCES games(id)
);
```

A user can resubmit and update their own entry before calculation.

### 5.3 `game_results`

```sql
CREATE TABLE game_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    telegram_user_id INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    net_before_commission_cents INTEGER NOT NULL,
    commission_paid_cents INTEGER NOT NULL,
    final_net_cents INTEGER NOT NULL,
    FOREIGN KEY(game_id) REFERENCES games(id)
);
```

### 5.4 `transactions`

```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    from_display_name TEXT NOT NULL,
    to_display_name TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    FOREIGN KEY(game_id) REFERENCES games(id)
);
```

### 5.5 `host_commission_stats`

This can be derived from `game_results`, but a simple table is useful for faster stats.

```sql
CREATE TABLE host_commission_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    host_user_id INTEGER NOT NULL,
    host_display_name TEXT NOT NULL,
    total_commission_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(game_id) REFERENCES games(id)
);
```

---

## 6. Bot Commands

### 6.1 `/newgame`

Creates a new active game in the group.

Rules:

- Only one active game per chat.
- The user who runs `/newgame` becomes host.
- Ask for settings using conversation flow:
  - chip value
  - commission percentage
  - buy-in mode

### 6.2 `/submit`

Allows current Telegram user to submit or update their own player entry.

Rules:

- Must have active game in current chat.
- Use Telegram `from_user.id` as player identity.
- Store name separately so users can choose display name.
- Validate numeric fields.

### 6.3 `/status`

Shows active game and current submissions.

### 6.4 `/calculate`

Finalizes the game.

Rules:

- Only host can calculate.
- Run settlement logic.
- Save results and transactions.
- Mark game as completed.
- Send final result message.

### 6.5 `/history`

Shows recent completed games in the chat.

Example:

```text
Recent games:
#12 — 2026-06-20 — Host: Chua — Commission: SGD 1.39
#11 — 2026-06-18 — Host: Samson — Commission: SGD 0.00
```

### 6.6 `/stats`

Shows host commission statistics.

Required stat:

```text
Total commission given to host across all completed games in this group: SGD 28.47
```

Optional extra stats:

```text
By host:
- Chua: SGD 21.37 across 9 games
- Samson: SGD 7.10 across 3 games
```

### 6.7 `/cancelgame`

Only host can cancel active game.

---

## 7. Inline UI Design

Use inline keyboards for common actions.

After `/newgame`, bot sends:

```text
Game #12 started.
```

Buttons:

```text
[Submit My Entry]
[View Status]
[Calculate Result - Host Only]
```

Callback data examples:

```text
submit_entry
view_status
calculate_game
```

For MVP, commands are enough. Inline buttons can call the same handler logic as commands.

---

## 8. Project Structure

Codex should create this structure:

```text
chips-settlement-bot/
├── README.md
├── plan.md
├── requirements.txt
├── .env.example
├── src/
│   └── chips_bot/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── db.py
│       ├── models.py
│       ├── settlement.py
│       ├── formatters.py
│       ├── handlers/
│       │   ├── __init__.py
│       │   ├── new_game.py
│       │   ├── submit.py
│       │   ├── status.py
│       │   ├── calculate.py
│       │   ├── history.py
│       │   └── stats.py
│       └── repositories/
│           ├── __init__.py
│           ├── games.py
│           ├── entries.py
│           └── results.py
└── tests/
    ├── test_settlement.py
    └── test_formatters.py
```

---

## 9. Required Implementation Details

### 9.1 `requirements.txt`

```text
python-telegram-bot>=22.0
python-dotenv>=1.0.0
SQLAlchemy>=2.0.0
pytest>=8.0.0
```

### 9.2 `.env.example`

```text
TELEGRAM_BOT_TOKEN=replace_me
DATABASE_URL=sqlite:///chips_bot.sqlite3
```

### 9.3 `config.py`

Load env vars:

```python
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
```

### 9.4 `settlement.py`

This file should be pure business logic and have no Telegram dependency.

Must include:

- Decimal parsing helpers
- cents conversion helper
- `calculate_settlement`
- `settle_transactions`
- validation that total final net is zero

Important formatting helper:

```python
def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}SGD {cents // 100}.{cents % 100:02d}"
```

---

## 10. Settlement Test Cases

Codex must implement tests before or alongside the bot handlers.

### 10.1 Basic no-commission case

Input:

```text
A: 300 chips, buy-in SGD 20, chip value 0.1 => +10
B: 100 chips, buy-in SGD 20, chip value 0.1 => -10
```

Expected:

```text
B pays A SGD 10.00
```

### 10.2 Commission case with host losing

Input:

```text
chip value = 0.1
commission = 2%
host = Chua

es: 562 chips, buy-in SGD 20 => +36.20
Gzs: 0 chips, buy-in SGD 20 => -20.00
Chua: 575 chips, buy-in SGD 60 => -2.50
```

Expected:

```text
es pays commission SGD 0.72
Chua receives commission SGD 0.72
es final net = +35.48
Chua final net = -1.78
```

### 10.3 Host also winning

Input:

```text
chip value = 0.1
commission = 2%
host = Chua

Chua: +50.00 before commission
A: +20.00 before commission
B: -70.00 before commission
```

Expected:

```text
Chua commission paid = 1.00
A commission paid = 0.40
Total commission to host = 1.40
Chua final = 50.00 - 1.00 + 1.40 = 50.40
A final = 19.60
B final = -70.00
Sum final = 0
```

### 10.4 Real-style multi-player case

Use this as a realistic integration test:

```text
chip value = 0.1
commission = 2%
host = Chua

es: 562 (200)
Gzg: 335 (200)
Gzs: 0 (200)
samson: 0 (400)
ziyi: 353 (200)
jervin: 635 (600)
chester: 610 (600)
ruvy: 136 (200)
gianice: 194 (200)
Chua: 575 (600)
```

Here numbers in parentheses are SGD buy-in amounts.

Expected net before commission:

```text
es +36.20
Gzg +13.50
Gzs -20.00
samson -40.00
ziyi +15.30
jervin +3.50
chester +1.00
ruvy -6.40
gianice -0.60
Chua -2.50
```

Expected total host commission:

```text
0.72 + 0.27 + 0.31 + 0.07 + 0.02 = SGD 1.39
```

Expected Chua final net:

```text
-2.50 + 1.39 = -1.11
```

---

## 11. Telegram Handler Implementation Notes

### 11.1 `main.py`

Create app:

```python
from telegram.ext import Application
from chips_bot.config import load_config


def main() -> None:
    config = load_config()
    app = Application.builder().token(config.telegram_bot_token).build()

    # register handlers here

    app.run_polling()


if __name__ == "__main__":
    main()
```

### 11.2 Conversation states

Use `ConversationHandler` for `/newgame` and `/submit`.

Example states:

```python
ASK_CHIP_VALUE = 1
ASK_COMMISSION = 2
ASK_BUY_IN_MODE = 3

ASK_NAME = 10
ASK_REMAINING_CHIPS = 11
ASK_BUY_IN = 12
CONFIRM_SUBMIT = 13
```

### 11.3 Permissions

To check host-only actions:

```python
if update.effective_user.id != game.host_user_id:
    await update.message.reply_text("Only the host can do this.")
    return
```

### 11.4 Group chat behavior

Use `chat_id = update.effective_chat.id` to scope games to each Telegram group.

This means different groups can have different active games at the same time.

---

## 12. Output Formatting

Create `formatters.py` to keep Telegram messages clean.

Functions:

```python
def format_status(game, entries) -> str:
    pass


def format_result(settlement_result) -> str:
    pass


def format_history(games) -> str:
    pass


def format_stats(stats) -> str:
    pass
```

Use Telegram-safe plain text. Avoid complex Markdown until escaping is implemented correctly.

Recommended final result format:

```text
Final Result — Game #12

Each chip = SGD 0.10
Host commission = 2%
Host = Chua

Net before commission:
- es: +SGD 36.20, commission SGD 0.72, final +SGD 35.48
- Gzg: +SGD 13.50, commission SGD 0.27, final +SGD 13.23
- Chua: -SGD 2.50, commission received SGD 1.39, final -SGD 1.11

Settlement:
- samson pays es SGD 35.48
- samson pays ziyi SGD 4.52

Host commission total: SGD 1.39
```

---

## 13. Edge Cases

Handle these carefully:

1. No active game.
2. User submits before `/newgame`.
3. Non-host tries `/calculate`.
4. Player submits negative chips or negative buy-in.
5. Player submits invalid number like `abc`.
6. Player resubmits; update their old entry.
7. Host is not in player entries; allow this, but warn that host commission still goes to host stats.
8. Host is also a player; common expected case.
9. Rounding differences of 1 cent.
10. All players break even.
11. Commission is 0%.
12. Commission is too high; cap valid range to `0 <= p <= 100`, but recommend normal values like `0`, `1`, `2`, `5`.

---

## 14. Deployment Plan

### 14.1 Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m chips_bot.main
```

### 14.2 Create Telegram bot

1. Message `@BotFather` on Telegram.
2. Create a new bot.
3. Copy the bot token.
4. Put token in `.env`.
5. Add bot to the target Telegram group.

### 14.3 Hosting options

For MVP:

- Run locally on laptop using polling.

For long-running bot:

- Deploy on a small VPS.
- Or use Railway / Render / Fly.io.
- Use polling first; webhook can be added later.

---

## 15. Milestones for Codex

### Milestone 1 — Pure settlement logic

Implement:

- `settlement.py`
- `tests/test_settlement.py`

No Telegram code yet.

### Milestone 2 — SQLite persistence

Implement:

- DB setup
- game repository
- entry repository
- result repository

### Milestone 3 — Basic Telegram commands

Implement:

- `/start`
- `/help`
- `/newgame`
- `/submit`
- `/status`
- `/calculate`

### Milestone 4 — History and stats

Implement:

- `/history`
- `/stats`
- total commission grouped by host
- total commission for current group

### Milestone 5 — Inline keyboard UI

Add buttons:

- Submit My Entry
- View Status
- Calculate Result

### Milestone 6 — Polish

Add:

- Better validation messages
- More tests
- README screenshots/examples
- Deployment guide

---

## 16. Acceptance Criteria

The bot is complete when:

1. A host can start a game in a Telegram group.
2. Players can submit name, chips remaining, and buy-in.
3. Host can calculate result.
4. Result includes net before commission, commission paid, final net, and transactions.
5. Host commission works even when host is also a player.
6. Game history is saved.
7. `/stats` shows total commission given to host across historical games.
8. Settlement logic is covered by tests.
9. All money calculations use integer cents or Decimal, never raw float.
10. Multiple groups can use the bot independently.

---

## 17. Important Instruction to Codex

Start by implementing and testing the pure settlement logic before writing Telegram handlers.

Do not mix Telegram code with calculation logic.

The settlement module should be fully testable using `pytest` without needing a Telegram bot token.
