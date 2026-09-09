from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings

_DB_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _migrate(conn: sqlite3.Connection) -> None:
    product_cols = _columns(conn, "products")
    if "stock" not in product_cols:
        conn.execute("ALTER TABLE products ADD COLUMN stock INTEGER NOT NULL DEFAULT 0")
    if "delivery_text" not in product_cols:
        conn.execute("ALTER TABLE products ADD COLUMN delivery_text TEXT NOT NULL DEFAULT ''")

    order_cols = _columns(conn, "orders")
    if "unique_code" not in order_cols:
        conn.execute("ALTER TABLE orders ADD COLUMN unique_code INTEGER NOT NULL DEFAULT 0")
    if "delivered_at" not in order_cols:
        conn.execute("ALTER TABLE orders ADD COLUMN delivered_at TEXT")


def init() -> None:
    with _DB_LOCK, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL DEFAULT '',
                first_name TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                price INTEGER NOT NULL CHECK(price > 0),
                stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
                delivery_text TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                telegram_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                unit_price INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                total_amount INTEGER NOT NULL,
                unique_code INTEGER NOT NULL DEFAULT 0,
                payment_method TEXT NOT NULL,
                status TEXT NOT NULL,
                klik_signature TEXT,
                qris_url TEXT,
                direct_url TEXT,
                expired_at TEXT,
                proof_file_id TEXT,
                admin_note TEXT,
                delivered_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_orders_telegram_id
                ON orders(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_orders_status_method
                ON orders(status, payment_method);
            """
        )
        _migrate(conn)
        _seed_products_if_empty(conn)


def _seed_products_if_empty(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count:
        return

    seed_path = Path("data/seed_products.json")
    if not seed_path.exists():
        return

    try:
        items = json.loads(seed_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    for item in items:
        name = str(item.get("name", "")).strip()
        price = int(item.get("price", 0))
        stock = int(item.get("stock", 0))
        if not name or price <= 0 or stock < 0:
            continue
        conn.execute(
            """
            INSERT INTO products(
                name, description, price, stock, delivery_text, active, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                str(item.get("description", "")).strip(),
                price,
                stock,
                str(item.get("delivery_text", "")).strip(),
                1 if item.get("active", True) else 0,
                _now(),
            ),
        )


def upsert_user(user: Any) -> None:
    now = _now()
    with _DB_LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO users(telegram_id, username, first_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                updated_at=excluded.updated_at
            """,
            (user.id, user.username or "", user.first_name or "", now, now),
        )


def products(active_only: bool = True):
    sql = "SELECT * FROM products"
    if active_only:
        sql += " WHERE active=1 AND stock>0"
    sql += " ORDER BY id"
    with _DB_LOCK, _connect() as conn:
        return conn.execute(sql).fetchall()


def product(product_id: int):
    with _DB_LOCK, _connect() as conn:
        return conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()


def add_product(
    name: str,
    description: str,
    price: int,
    stock: int,
    delivery_text: str,
) -> int:
    with _DB_LOCK, _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO products(
                name, description, price, stock, delivery_text, active, created_at
            )
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (
                name.strip(),
                description.strip(),
                int(price),
                int(stock),
                delivery_text.strip(),
                _now(),
            ),
        )
        return int(cur.lastrowid)


def set_stock(product_id: int, stock: int) -> bool:
    with _DB_LOCK, _connect() as conn:
        cur = conn.execute(
            "UPDATE products SET stock=? WHERE id=?",
            (max(0, int(stock)), product_id),
        )
        return cur.rowcount == 1


def create_order(
    order_id: str,
    telegram_id: int,
    product_row,
    quantity: int,
    amount: int,
    total_amount: int,
    unique_code: int,
    payment_method: str,
) -> None:
    now = _now()
    with _DB_LOCK, _connect() as conn:
        current = conn.execute(
            "SELECT active, stock FROM products WHERE id=?",
            (product_row["id"],),
        ).fetchone()
        if not current or not current["active"]:
            raise ValueError("Product is not active")
        if int(current["stock"]) < int(quantity):
            raise ValueError("Insufficient stock")

        conn.execute(
            """
            INSERT INTO orders(
                order_id, telegram_id, product_id, product_name, unit_price,
                quantity, amount, total_amount, unique_code, payment_method,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
            """,
            (
                order_id,
                telegram_id,
                product_row["id"],
                product_row["name"],
                product_row["price"],
                quantity,
                amount,
                total_amount,
                unique_code,
                payment_method,
                now,
                now,
            ),
        )


def order(order_id: str):
    with _DB_LOCK, _connect() as conn:
        return conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()


def recent(limit: int = 20):
    limit = max(1, min(int(limit), 100))
    with _DB_LOCK, _connect() as conn:
        return conn.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()


def latest_pending_for_user(telegram_id: int):
    with _DB_LOCK, _connect() as conn:
        return conn.execute(
            """
            SELECT * FROM orders
            WHERE telegram_id=? AND status='PENDING'
            ORDER BY id DESC LIMIT 1
            """,
            (telegram_id,),
        ).fetchone()


def pending_total_exists(total_amount: int) -> bool:
    """Return True if another pending order already uses this exact payable total."""
    with _DB_LOCK, _connect() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM orders
            WHERE status='PENDING' AND total_amount=?
            LIMIT 1
            """,
            (int(total_amount),),
        ).fetchone()
        return row is not None


def add_proof(order_id: str, file_id: str) -> None:
    with _DB_LOCK, _connect() as conn:
        conn.execute(
            """
            UPDATE orders
            SET proof_file_id=?, updated_at=?
            WHERE order_id=?
            """,
            (file_id, _now(), order_id),
        )


def cancel(order_id: str) -> bool:
    with _DB_LOCK, _connect() as conn:
        cur = conn.execute(
            """
            UPDATE orders
            SET status='CANCELLED', updated_at=?
            WHERE order_id=? AND status='PENDING'
            """,
            (_now(), order_id),
        )
        return cur.rowcount == 1


def confirm_paid_and_take_stock(order_id: str) -> tuple[bool, str]:
    """
    Atomically:
    - checks PENDING order
    - checks product stock
    - decrements stock by order quantity
    - marks order PAID

    Returns (success, reason).
    """
    with _DB_LOCK, _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id=?",
            (order_id,),
        ).fetchone()

        if not row:
            conn.rollback()
            return False, "ORDER_NOT_FOUND"
        if row["status"] != "PENDING":
            conn.rollback()
            return False, f"ORDER_{row['status']}"

        prod = conn.execute(
            "SELECT * FROM products WHERE id=?",
            (row["product_id"],),
        ).fetchone()

        if not prod:
            conn.rollback()
            return False, "PRODUCT_NOT_FOUND"
        if int(prod["stock"]) < int(row["quantity"]):
            conn.rollback()
            return False, "INSUFFICIENT_STOCK"

        conn.execute(
            "UPDATE products SET stock=stock-? WHERE id=?",
            (row["quantity"], row["product_id"]),
        )
        conn.execute(
            """
            UPDATE orders
            SET status='PAID', admin_note='Admin confirmed DANA Business QRIS',
                updated_at=?
            WHERE order_id=?
            """,
            (_now(), order_id),
        )
        conn.commit()
        return True, "OK"


def mark_delivered(order_id: str) -> None:
    with _DB_LOCK, _connect() as conn:
        conn.execute(
            """
            UPDATE orders
            SET delivered_at=?, updated_at=?
            WHERE order_id=?
            """,
            (_now(), _now(), order_id),
        )


def healthcheck() -> bool:
    try:
        with _DB_LOCK, _connect() as conn:
            return conn.execute("SELECT 1").fetchone()[0] == 1
    except sqlite3.Error:
        return False
