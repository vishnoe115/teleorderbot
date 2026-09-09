from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".env", override=False)
load_dotenv("config.env", override=False)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    admin_user_id: int

    payment_channel_id: str
    owner_mention_label: str
    owner_mention_username: str

    dana_business_name: str
    dana_business_qris_image: Path

    unique_code_min: int
    unique_code_max: int

    db_path: Path
    log_file: Path
    log_level: str

    host: str
    port: int


def load_settings() -> Settings:
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        admin_user_id=_int("ADMIN_USER_ID", 0),

        payment_channel_id=os.getenv("PAYMENT_CHANNEL_ID", "").strip(),
        owner_mention_label=os.getenv("OWNER_MENTION_LABEL", "Owner").strip() or "Owner",
        owner_mention_username=os.getenv("OWNER_MENTION_USERNAME", "").strip().lstrip("@"),

        dana_business_name=os.getenv("DANA_BUSINESS_NAME", "").strip(),
        dana_business_qris_image=Path(
            os.getenv("DANA_BUSINESS_QRIS_IMAGE", "./data/dana_business_qris.png")
        ),

        # Three-digit tracking code, regenerated for every order.
        unique_code_min=_int("UNIQUE_CODE_MIN", 100),
        unique_code_max=_int("UNIQUE_CODE_MAX", 400),

        db_path=Path(os.getenv("DB_PATH", "./data/orders.db")),
        log_file=Path(os.getenv("LOG_FILE", "./logs/bot.log")),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),

        host=os.getenv("HOST", "0.0.0.0").strip(),
        port=_int("PORT", 8080),
    )


def validate_settings(s: Settings) -> None:
    if not s.bot_token:
        raise RuntimeError("BOT_TOKEN is required")
    if s.admin_user_id <= 0:
        raise RuntimeError("ADMIN_USER_ID must be a valid Telegram numeric user ID")
    if not s.dana_business_name:
        raise RuntimeError("DANA_BUSINESS_NAME is required")
    if not (100 <= s.unique_code_min <= 400):
        raise RuntimeError("UNIQUE_CODE_MIN must be between 100 and 400")
    if not (100 <= s.unique_code_max <= 400):
        raise RuntimeError("UNIQUE_CODE_MAX must be between 100 and 400")
    if s.unique_code_max < s.unique_code_min:
        raise RuntimeError("UNIQUE_CODE_MAX must be >= UNIQUE_CODE_MIN")
    if not (1 <= s.port <= 65535):
        raise RuntimeError("PORT must be between 1 and 65535")


settings = load_settings()
