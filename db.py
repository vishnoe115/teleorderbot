from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.errors import PyMongoError

from config import settings

_client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
_mongo = _client[settings.mongodb_database]
_users = _mongo["users"]
_products = _mongo["products"]
_orders = _mongo["orders"]
_counters = _mongo["counters"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _next_id(name: str) -> int:
    row = _counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(row["seq"])


def _public(document: dict | None):
    if not document:
        return None
    result = dict(document)
    result.pop("_id", None)
    return result


def init() -> None:
    _client.admin.command("ping")

    _users.create_index([("telegram_id", ASCENDING)], unique=True)
    _products.create_index([("id", ASCENDING)], unique=True)
    _products.create_index([("active", ASCENDING), ("stock", DESCENDING)])
    _orders.create_index([("order_id", ASCENDING)], unique=True)
    _orders.create_index([("telegram_id", ASCENDING), ("created_at", DESCENDING)])
    _orders.create_index([("status", ASCENDING), ("total_amount", ASCENDING)])

    _migrate_legacy_products_if_needed()
    _seed_products_if_empty()


def _migrate_legacy_products_if_needed() -> None:
    """Import legacy SQLite products once when MongoDB has no products yet."""
    if _products.count_documents({}) > 0:
        return

    legacy_path = Path("data/orders.db")
    if not legacy_path.exists():
        return

    try:
        conn = sqlite3.connect(legacy_path)
        conn.row_factory = sqlite3.Row
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='products'"
        ).fetchone()
        if not table:
            conn.close()
            return

        rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
        max_id = 0
        for row in rows:
            product_id = int(row["id"])
            max_id = max(max_id, product_id)
            _products.update_one(
                {"id": product_id},
                {
                    "$setOnInsert": {
                        "id": product_id,
                        "name": str(row["name"]),
                        "description": str(row["description"] or ""),
                        "price": int(row["price"]),
                        "stock": int(row["stock"] if "stock" in row.keys() else 0),
                        "delivery_text": str(row["delivery_text"] if "delivery_text" in row.keys() else ""),
                        "active": bool(row["active"]),
                        "created_at": _now(),
                        "updated_at": _now(),
                    }
                },
                upsert=True,
            )
        conn.close()
        if max_id:
            _counters.update_one(
                {"_id": "products"},
                {"$max": {"seq": max_id}},
                upsert=True,
            )
    except sqlite3.Error:
        return


def _seed_products_if_empty() -> None:
    if _products.count_documents({}) > 0:
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
        add_product(
            name=name,
            description=str(item.get("description", "")).strip(),
            price=price,
            stock=stock,
            delivery_text=str(item.get("delivery_text", "")).strip(),
            active=bool(item.get("active", True)),
        )


def upsert_user(user: Any) -> None:
    now = _now()
    _users.update_one(
        {"telegram_id": int(user.id)},
        {
            "$set": {
                "username": user.username or "",
                "first_name": user.first_name or "",
                "updated_at": now,
            },
            "$setOnInsert": {
                "telegram_id": int(user.id),
                "created_at": now,
            },
        },
        upsert=True,
    )


def products(active_only: bool = True):
    query = {"active": True, "stock": {"$gt": 0}} if active_only else {}
    return [_public(row) for row in _products.find(query).sort("id", ASCENDING)]


def product(product_id: int):
    return _public(_products.find_one({"id": int(product_id)}))


def add_product(
    name: str,
    description: str,
    price: int,
    stock: int,
    delivery_text: str,
    active: bool = True,
) -> int:
    product_id = _next_id("products")
    _products.insert_one(
        {
            "id": product_id,
            "name": name.strip(),
            "description": description.strip(),
            "price": int(price),
            "stock": max(0, int(stock)),
            "delivery_text": delivery_text.strip(),
            "active": bool(active),
            "created_at": _now(),
            "updated_at": _now(),
        }
    )
    return product_id


def set_stock(product_id: int, stock: int) -> bool:
    result = _products.update_one(
        {"id": int(product_id)},
        {"$set": {"stock": max(0, int(stock)), "updated_at": _now()}},
    )
    return result.matched_count == 1


def product_has_pending_orders(product_id: int) -> bool:
    return _orders.find_one(
        {"product_id": int(product_id), "status": "PENDING"},
        {"_id": 1},
    ) is not None


def delete_product(product_id: int) -> bool:
    """Permanently delete a product from MongoDB.

    Historical orders remain intact because order rows store product name/price snapshots.
    """
    result = _products.delete_one({"id": int(product_id)})
    return result.deleted_count == 1


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
    current = _products.find_one({"id": int(product_row["id"]), "active": True})
    if not current:
        raise ValueError("Product is not active")
    if int(current.get("stock", 0)) < int(quantity):
        raise ValueError("Insufficient stock")

    now = _now()
    _orders.insert_one(
        {
            "order_id": order_id,
            "telegram_id": int(telegram_id),
            "product_id": int(product_row["id"]),
            "product_name": product_row["name"],
            "unit_price": int(product_row["price"]),
            "quantity": int(quantity),
            "amount": int(amount),
            "total_amount": int(total_amount),
            "unique_code": int(unique_code),
            "payment_method": payment_method,
            "status": "PENDING",
            "proof_file_id": None,
            "admin_note": None,
            "delivered_at": None,
            "created_at": now,
            "updated_at": now,
        }
    )


def order(order_id: str):
    return _public(_orders.find_one({"order_id": order_id}))


def recent(limit: int = 20):
    limit = max(1, min(int(limit), 100))
    return [
        _public(row)
        for row in _orders.find({}).sort("created_at", DESCENDING).limit(limit)
    ]


def latest_pending_for_user(telegram_id: int):
    return _public(
        _orders.find_one(
            {"telegram_id": int(telegram_id), "status": "PENDING"},
            sort=[("created_at", DESCENDING)],
        )
    )


def pending_total_exists(total_amount: int) -> bool:
    return _orders.find_one(
        {"status": "PENDING", "total_amount": int(total_amount)},
        {"_id": 1},
    ) is not None


def add_proof(order_id: str, file_id: str) -> None:
    _orders.update_one(
        {"order_id": order_id},
        {"$set": {"proof_file_id": file_id, "updated_at": _now()}},
    )


def cancel(order_id: str) -> bool:
    result = _orders.update_one(
        {"order_id": order_id, "status": "PENDING"},
        {"$set": {"status": "CANCELLED", "updated_at": _now()}},
    )
    return result.modified_count == 1


def confirm_paid_and_take_stock(order_id: str) -> tuple[bool, str]:
    """Reserve stock with an atomic MongoDB update, then mark the order PAID.

    Product stock decrement is guarded by stock >= quantity, so stock cannot go negative.
    If the order status update unexpectedly fails, stock is compensated immediately.
    """
    row = _orders.find_one({"order_id": order_id})
    if not row:
        return False, "ORDER_NOT_FOUND"
    if row.get("status") != "PENDING":
        return False, f"ORDER_{row.get('status', 'UNKNOWN')}"

    quantity = int(row["quantity"])
    product_id = int(row["product_id"])

    reserved = _products.find_one_and_update(
        {
            "id": product_id,
            "active": True,
            "stock": {"$gte": quantity},
        },
        {
            "$inc": {"stock": -quantity},
            "$set": {"updated_at": _now()},
        },
        return_document=ReturnDocument.AFTER,
    )
    if not reserved:
        if _products.find_one({"id": product_id}) is None:
            return False, "PRODUCT_NOT_FOUND"
        return False, "INSUFFICIENT_STOCK"

    result = _orders.update_one(
        {"order_id": order_id, "status": "PENDING"},
        {
            "$set": {
                "status": "PAID",
                "admin_note": "Admin confirmed DANA Business QRIS",
                "updated_at": _now(),
            }
        },
    )

    if result.modified_count != 1:
        _products.update_one(
            {"id": product_id},
            {"$inc": {"stock": quantity}, "$set": {"updated_at": _now()}},
        )
        current = _orders.find_one({"order_id": order_id})
        return False, f"ORDER_{current.get('status', 'UNKNOWN') if current else 'NOT_FOUND'}"

    return True, "OK"


def mark_delivered(order_id: str) -> None:
    now = _now()
    _orders.update_one(
        {"order_id": order_id},
        {"$set": {"delivered_at": now, "updated_at": now}},
    )


def healthcheck() -> bool:
    try:
        return bool(_client.admin.command("ping").get("ok"))
    except PyMongoError:
        return False
