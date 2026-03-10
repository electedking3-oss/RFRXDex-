import sqlite3
import os
import json
import random
from datetime import datetime, date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "rfrxdex.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id      TEXT PRIMARY KEY,
            username     TEXT,
            coins        INTEGER DEFAULT 500,
            total_caught INTEGER DEFAULT 0,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            card_id     TEXT NOT NULL,
            variant     TEXT DEFAULT 'Standard',
            catch_value INTEGER DEFAULT 0,
            caught_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            instance_id TEXT UNIQUE,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS info_cards (
            user_id    TEXT NOT NULL,
            card_id    TEXT NOT NULL,
            granted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, card_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS market_listings (
            listing_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id   TEXT NOT NULL,
            card_id     TEXT NOT NULL,
            variant     TEXT DEFAULT 'Standard',
            instance_id TEXT NOT NULL,
            price       INTEGER NOT NULL,
            listed_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            status      TEXT DEFAULT 'active',
            buyer_id    TEXT,
            sold_at     TEXT,
            FOREIGN KEY(seller_id) REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            trade_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            initiator_id  TEXT NOT NULL,
            target_id     TEXT NOT NULL,
            offer_cards   TEXT DEFAULT '[]',
            request_cards TEXT DEFAULT '[]',
            status        TEXT DEFAULT 'pending',
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at   TEXT,
            FOREIGN KEY(initiator_id) REFERENCES users(user_id),
            FOREIGN KEY(target_id)   REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS auctions (
            auction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id    TEXT NOT NULL,
            card_id      TEXT NOT NULL,
            variant      TEXT DEFAULT 'Standard',
            instance_id  TEXT NOT NULL,
            starting_bid INTEGER NOT NULL DEFAULT 1,
            buyout_price INTEGER,
            current_bid  INTEGER DEFAULT 0,
            top_bidder   TEXT,
            status       TEXT DEFAULT 'active',
            ends_at      TEXT NOT NULL,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS auction_bids (
            bid_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            auction_id INTEGER NOT NULL,
            bidder_id  TEXT NOT NULL,
            amount     INTEGER NOT NULL,
            bid_at     TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS battles (
            battle_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            challenger_id TEXT NOT NULL,
            opponent_id   TEXT NOT NULL,
            wage          INTEGER DEFAULT 0,
            status        TEXT DEFAULT 'pending',
            winner_id     TEXT,
            log           TEXT DEFAULT '[]',
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at   TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS battle_rosters (
            user_id     TEXT NOT NULL,
            slot        INTEGER NOT NULL,
            roster_type TEXT NOT NULL DEFAULT 'Offense',
            instance_id TEXT,
            PRIMARY KEY(user_id, slot)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS card_history (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id          TEXT NOT NULL,
            variant          TEXT DEFAULT 'Standard',
            price            INTEGER NOT NULL,
            transaction_type TEXT,
            seller_id        TEXT,
            buyer_id         TEXT,
            recorded_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_values (
            card_id    TEXT NOT NULL,
            variant    TEXT DEFAULT 'Standard',
            value_date TEXT NOT NULL,
            avg_price  INTEGER,
            min_price  INTEGER,
            max_price  INTEGER,
            num_sales  INTEGER DEFAULT 0,
            PRIMARY KEY(card_id, variant, value_date)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS card_values (
            card_id      TEXT NOT NULL,
            variant      TEXT DEFAULT 'Standard',
            current_value INTEGER NOT NULL,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(card_id, variant)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS spawns (
            spawn_id   TEXT PRIMARY KEY,
            card_id    TEXT NOT NULL,
            variant    TEXT DEFAULT 'Standard',
            channel_id TEXT NOT NULL,
            message_id TEXT,
            caught_by  TEXT,
            caught_at  TEXT,
            spawned_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active  INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized.")


# ── USER ─────────────────────────────────────────────────────────────────────

def ensure_user(user_id: str, username: str = ""):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (str(user_id), username))
    conn.commit()
    conn.close()

def get_user(user_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (str(user_id),)).fetchone()
    conn.close()
    return dict(row) if row else None

def add_coins(user_id: str, amount: int):
    conn = get_conn()
    conn.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, str(user_id)))
    conn.commit()
    conn.close()

def deduct_coins(user_id: str, amount: int) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT coins FROM users WHERE user_id = ?", (str(user_id),)).fetchone()
    if not row or row["coins"] < amount:
        conn.close()
        return False
    conn.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (amount, str(user_id)))
    conn.commit()
    conn.close()
    return True


# ── INVENTORY ────────────────────────────────────────────────────────────────

def add_card_to_inventory(user_id: str, card_id: str, variant: str, catch_value: int, instance_id: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO inventory (user_id, card_id, variant, catch_value, instance_id) VALUES (?, ?, ?, ?, ?)",
        (str(user_id), card_id, variant, catch_value, instance_id)
    )
    conn.execute("UPDATE users SET total_caught = total_caught + 1 WHERE user_id = ?", (str(user_id),))
    conn.commit()
    conn.close()

def remove_card_from_inventory(instance_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM inventory WHERE instance_id = ?", (instance_id,))
    conn.commit()
    conn.close()

def get_user_inventory(user_id: str):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM inventory WHERE user_id = ? ORDER BY caught_at DESC", (str(user_id),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_inventory_instance(instance_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM inventory WHERE instance_id = ?", (instance_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def transfer_card(instance_id: str, new_owner_id: str):
    conn = get_conn()
    conn.execute("UPDATE inventory SET user_id = ? WHERE instance_id = ?", (str(new_owner_id), instance_id))
    conn.execute("UPDATE users SET total_caught = total_caught + 1 WHERE user_id = ?", (str(new_owner_id),))
    conn.commit()
    conn.close()

def user_has_card(user_id: str, card_id: str, variant: str = None) -> bool:
    conn = get_conn()
    if variant:
        row = conn.execute("SELECT id FROM inventory WHERE user_id = ? AND card_id = ? AND variant = ?", (str(user_id), card_id, variant)).fetchone()
    else:
        row = conn.execute("SELECT id FROM inventory WHERE user_id = ? AND card_id = ?", (str(user_id), card_id)).fetchone()
    conn.close()
    return row is not None


# ── INFO CARDS ───────────────────────────────────────────────────────────────

def grant_info_card(user_id: str, card_id: str):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO info_cards (user_id, card_id) VALUES (?, ?)", (str(user_id), card_id))
    conn.commit()
    conn.close()

def get_user_info_cards(user_id: str):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM info_cards WHERE user_id = ?", (str(user_id),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── MARKET ───────────────────────────────────────────────────────────────────

def create_listing(seller_id: str, card_id: str, variant: str, instance_id: str, price: int) -> int:
    conn = get_conn()
    c = conn.execute(
        "INSERT INTO market_listings (seller_id, card_id, variant, instance_id, price) VALUES (?, ?, ?, ?, ?)",
        (str(seller_id), card_id, variant, instance_id, price)
    )
    lid = c.lastrowid
    conn.commit()
    conn.close()
    return lid

def get_active_listings(card_id: str = None):
    conn = get_conn()
    if card_id:
        rows = conn.execute("SELECT * FROM market_listings WHERE status = 'active' AND card_id = ? ORDER BY price ASC", (card_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM market_listings WHERE status = 'active' ORDER BY listed_at DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def complete_listing(listing_id: int, buyer_id: str):
    conn = get_conn()
    listing = conn.execute("SELECT * FROM market_listings WHERE listing_id = ? AND status = 'active'", (listing_id,)).fetchone()
    if not listing:
        conn.close()
        return None
    conn.execute("UPDATE market_listings SET status = 'sold', buyer_id = ?, sold_at = CURRENT_TIMESTAMP WHERE listing_id = ?", (str(buyer_id), listing_id))
    conn.commit()
    conn.close()
    return dict(listing)

def cancel_listing(listing_id: int, seller_id: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT * FROM market_listings WHERE listing_id = ? AND seller_id = ? AND status = 'active'", (listing_id, str(seller_id))).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute("UPDATE market_listings SET status = 'cancelled' WHERE listing_id = ?", (listing_id,))
    conn.commit()
    conn.close()
    return True


# ── AUCTIONS ─────────────────────────────────────────────────────────────────

def create_auction(seller_id: str, card_id: str, variant: str, instance_id: str,
                   starting_bid: int, duration_hours: int, buyout_price: int = None) -> int:
    conn = get_conn()
    ends_at = (datetime.utcnow() + timedelta(hours=duration_hours)).isoformat()
    c = conn.execute(
        """INSERT INTO auctions (seller_id, card_id, variant, instance_id, starting_bid, buyout_price, current_bid, ends_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (str(seller_id), card_id, variant, instance_id, starting_bid, buyout_price, starting_bid, ends_at)
    )
    aid = c.lastrowid
    conn.commit()
    conn.close()
    return aid

def get_auction(auction_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM auctions WHERE auction_id = ?", (auction_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_active_auctions():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM auctions WHERE status = 'active' ORDER BY ends_at ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def place_bid(auction_id: int, bidder_id: str, amount: int) -> bool:
    conn = get_conn()
    auction = conn.execute("SELECT * FROM auctions WHERE auction_id = ? AND status = 'active'", (auction_id,)).fetchone()
    if not auction or amount <= auction["current_bid"]:
        conn.close()
        return False
    conn.execute("UPDATE auctions SET current_bid = ?, top_bidder = ? WHERE auction_id = ?", (amount, str(bidder_id), auction_id))
    conn.execute("INSERT INTO auction_bids (auction_id, bidder_id, amount) VALUES (?, ?, ?)", (auction_id, str(bidder_id), amount))
    conn.commit()
    conn.close()
    return True

def cancel_auction(auction_id: int, seller_id: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT * FROM auctions WHERE auction_id = ? AND seller_id = ? AND status = 'active'", (auction_id, str(seller_id))).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute("UPDATE auctions SET status = 'cancelled' WHERE auction_id = ?", (auction_id,))
    conn.commit()
    conn.close()
    return True

def get_user_bids(user_id: str):
    """Auctions where user has bid but hasn't won yet."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT a.* FROM auctions a
        JOIN auction_bids ab ON a.auction_id = ab.auction_id
        WHERE ab.bidder_id = ? AND a.status = 'active'
        ORDER BY a.ends_at ASC
    """, (str(user_id),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_auction_listings(user_id: str):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM auctions WHERE seller_id = ? AND status = 'active' ORDER BY ends_at ASC", (str(user_id),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_auction_history(user_id: str):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM auctions
        WHERE (seller_id = ? OR top_bidder = ?) AND status != 'active'
        ORDER BY created_at DESC LIMIT 20
    """, (str(user_id), str(user_id))).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── BATTLES ──────────────────────────────────────────────────────────────────

def create_battle(challenger_id: str, opponent_id: str, wage: int) -> int:
    conn = get_conn()
    c = conn.execute(
        "INSERT INTO battles (challenger_id, opponent_id, wage) VALUES (?, ?, ?)",
        (str(challenger_id), str(opponent_id), wage)
    )
    bid = c.lastrowid
    conn.commit()
    conn.close()
    return bid

def get_battle(battle_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM battles WHERE battle_id = ?", (battle_id,)).fetchone()
    conn.close()
    if not row:
        return None
    b = dict(row)
    b["log"] = json.loads(b["log"])
    return b

def resolve_battle(battle_id: int, winner_id: str, log: list):
    conn = get_conn()
    conn.execute(
        "UPDATE battles SET status = 'completed', winner_id = ?, log = ?, resolved_at = CURRENT_TIMESTAMP WHERE battle_id = ?",
        (str(winner_id), json.dumps(log), battle_id)
    )
    conn.commit()
    conn.close()

def decline_battle(battle_id: int):
    conn = get_conn()
    conn.execute("UPDATE battles SET status = 'declined', resolved_at = CURRENT_TIMESTAMP WHERE battle_id = ?", (battle_id,))
    conn.commit()
    conn.close()


# ── BATTLE ROSTERS ────────────────────────────────────────────────────────────

def get_roster(user_id: str) -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM battle_rosters WHERE user_id = ? ORDER BY slot ASC", (str(user_id),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_roster_slot(user_id: str, slot: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM battle_rosters WHERE user_id = ? AND slot = ?", (str(user_id), slot)).fetchone()
    conn.close()
    return dict(row) if row else None

def set_roster_slot(user_id: str, slot: int, roster_type: str, instance_id: str = None):
    conn = get_conn()
    conn.execute("""
        INSERT INTO battle_rosters (user_id, slot, roster_type, instance_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, slot) DO UPDATE SET roster_type = ?, instance_id = ?
    """, (str(user_id), slot, roster_type, instance_id, roster_type, instance_id))
    conn.commit()
    conn.close()

def clear_roster_slot(user_id: str, slot: int):
    conn = get_conn()
    conn.execute("DELETE FROM battle_rosters WHERE user_id = ? AND slot = ?", (str(user_id), slot))
    conn.commit()
    conn.close()

def init_roster(user_id: str):
    """Create default 3 roster slots if they don't exist."""
    types = ["Offense", "Defense", "Balance"]
    conn = get_conn()
    for i, t in enumerate(types, 1):
        conn.execute("""
            INSERT OR IGNORE INTO battle_rosters (user_id, slot, roster_type, instance_id)
            VALUES (?, ?, ?, NULL)
        """, (str(user_id), i, t))
    conn.commit()
    conn.close()


# ── CARD VALUES / HISTORY ────────────────────────────────────────────────────

def get_current_value(card_id: str, variant: str = "Standard", base_value: int = 100) -> int:
    conn = get_conn()
    row = conn.execute("SELECT current_value FROM card_values WHERE card_id = ? AND variant = ?", (card_id, variant)).fetchone()
    conn.close()
    return row["current_value"] if row else base_value

def set_current_value(card_id: str, variant: str, value: int):
    conn = get_conn()
    conn.execute("""INSERT INTO card_values (card_id, variant, current_value)
                    VALUES (?, ?, ?)
                    ON CONFLICT(card_id, variant) DO UPDATE SET current_value = ?, last_updated = CURRENT_TIMESTAMP""",
                 (card_id, variant, value, value))
    conn.commit()
    conn.close()

def update_dynamic_price(card_id: str, variant: str, base_value: int, transaction_price: int):
    current = get_current_value(card_id, variant, base_value)
    new_val = int(current * 0.70 + transaction_price * 0.30)
    drift = random.uniform(-0.02, 0.02)
    new_val = max(int(base_value * 0.1), int(new_val * (1 + drift)))
    set_current_value(card_id, variant, new_val)
    return new_val

def record_sale(card_id: str, variant: str, price: int, seller_id: str, buyer_id: str):
    conn = get_conn()
    conn.execute("INSERT INTO card_history (card_id, variant, price, transaction_type, seller_id, buyer_id) VALUES (?, ?, ?, 'sale', ?, ?)",
                 (card_id, variant, price, str(seller_id), str(buyer_id)))
    today = date.today().isoformat()
    existing = conn.execute("SELECT * FROM daily_values WHERE card_id = ? AND variant = ? AND value_date = ?", (card_id, variant, today)).fetchone()
    if existing:
        conn.execute("""UPDATE daily_values SET
            avg_price = (avg_price * num_sales + ?) / (num_sales + 1),
            min_price = MIN(min_price, ?), max_price = MAX(max_price, ?), num_sales = num_sales + 1
            WHERE card_id = ? AND variant = ? AND value_date = ?""", (price, price, price, card_id, variant, today))
    else:
        conn.execute("INSERT INTO daily_values (card_id, variant, value_date, avg_price, min_price, max_price, num_sales) VALUES (?, ?, ?, ?, ?, ?, 1)",
                     (card_id, variant, today, price, price, price))
    conn.commit()
    conn.close()

def get_card_history_stats(card_id: str, variant: str = "Standard") -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT price FROM card_history WHERE card_id = ? AND variant = ? AND transaction_type = 'sale'", (card_id, variant)).fetchall()
    prices = [r["price"] for r in rows]
    owners = conn.execute("SELECT COUNT(DISTINCT buyer_id) as cnt FROM card_history WHERE card_id = ? AND variant = ?", (card_id, variant)).fetchone()
    daily = conn.execute("SELECT * FROM daily_values WHERE card_id = ? AND variant = ? ORDER BY value_date DESC LIMIT 30", (card_id, variant)).fetchall()
    conn.close()
    if not prices:
        return {"total_sales": 0, "total_owners": 0, "min": 0, "max": 0, "avg": 0, "daily": []}
    return {"total_sales": len(prices), "total_owners": owners["cnt"] if owners else 0,
            "min": min(prices), "max": max(prices), "avg": int(sum(prices) / len(prices)),
            "daily": [dict(r) for r in daily]}


# ── TRADES ───────────────────────────────────────────────────────────────────

def create_trade(initiator_id: str, target_id: str, offer_cards: list, request_cards: list) -> int:
    conn = get_conn()
    c = conn.execute("INSERT INTO trades (initiator_id, target_id, offer_cards, request_cards) VALUES (?, ?, ?, ?)",
                     (str(initiator_id), str(target_id), json.dumps(offer_cards), json.dumps(request_cards)))
    tid = c.lastrowid
    conn.commit()
    conn.close()
    return tid

def get_trade(trade_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
    conn.close()
    if not row:
        return None
    t = dict(row)
    t["offer_cards"] = json.loads(t["offer_cards"])
    t["request_cards"] = json.loads(t["request_cards"])
    return t

def resolve_trade(trade_id: int, status: str):
    conn = get_conn()
    conn.execute("UPDATE trades SET status = ?, resolved_at = CURRENT_TIMESTAMP WHERE trade_id = ?", (status, trade_id))
    conn.commit()
    conn.close()


# ── LEADERBOARDS ─────────────────────────────────────────────────────────────

def leaderboard_collectors(limit: int = 10):
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.user_id, u.username, COUNT(i.id) as card_count
        FROM users u LEFT JOIN inventory i ON u.user_id = i.user_id
        GROUP BY u.user_id ORDER BY card_count DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def leaderboard_wealth(limit: int = 10):
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.user_id, u.username,
               SUM(COALESCE(cv.current_value, i.catch_value)) as total_value
        FROM users u
        LEFT JOIN inventory i ON u.user_id = i.user_id
        LEFT JOIN card_values cv ON i.card_id = cv.card_id AND i.variant = cv.variant
        GROUP BY u.user_id ORDER BY total_value DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def leaderboard_rare(limit: int = 10):
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.user_id, u.username,
               COUNT(CASE WHEN i.variant IN ('Secret Rare','Ultra Rare','Shiny','DOTD','GP Specs','Collectors Special') THEN 1 END) as rare_count
        FROM users u LEFT JOIN inventory i ON u.user_id = i.user_id
        GROUP BY u.user_id ORDER BY rare_count DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── SPAWNS ───────────────────────────────────────────────────────────────────

def register_spawn(spawn_id: str, card_id: str, variant: str, channel_id: str):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO spawns (spawn_id, card_id, variant, channel_id) VALUES (?, ?, ?, ?)",
                 (spawn_id, card_id, variant, str(channel_id)))
    conn.commit()
    conn.close()

def update_spawn_message(spawn_id: str, message_id: str):
    conn = get_conn()
    conn.execute("UPDATE spawns SET message_id = ? WHERE spawn_id = ?", (str(message_id), spawn_id))
    conn.commit()
    conn.close()

def claim_spawn(spawn_id: str, user_id: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT * FROM spawns WHERE spawn_id = ? AND is_active = 1 AND caught_by IS NULL", (spawn_id,)).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute("UPDATE spawns SET caught_by = ?, caught_at = CURRENT_TIMESTAMP, is_active = 0 WHERE spawn_id = ?", (str(user_id), spawn_id))
    conn.commit()
    conn.close()
    return True

def get_spawn(spawn_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM spawns WHERE spawn_id = ?", (spawn_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
