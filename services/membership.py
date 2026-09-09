from __future__ import annotations

import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config import settings

log = logging.getLogger(__name__)


def membership_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 Gabung Channel", url=settings.required_channel_url)],
            [InlineKeyboardButton("✅ Saya Sudah Bergabung", callback_data="check_membership")],
        ]
    )


async def is_required_channel_member(bot: Bot, user_id: int) -> bool:
    # Owner/admin is never blocked by the customer membership gate.
    if int(user_id) == int(settings.admin_user_id):
        return True

    try:
        member = await bot.get_chat_member(settings.payment_channel_id, user_id)
    except TelegramError:
        log.exception(
            "Unable to check membership for user=%s channel=%s",
            user_id,
            settings.payment_channel_id,
        )
        return False

    status = str(getattr(member, "status", "")).lower()
    if status in {"creator", "administrator", "member", "owner"}:
        return True
    if status == "restricted":
        return bool(getattr(member, "is_member", False))
    return False


async def ensure_required_channel_member(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    user = update.effective_user
    if not user:
        return False

    if await is_required_channel_member(context.bot, user.id):
        return True

    text = (
        "🔒 <b>Akses bot belum dibuka</b>\n\n"
        f"Sebelum menggunakan bot, Anda wajib bergabung dengan "
        f"<b>{settings.required_channel_name}</b>. Channel ini juga digunakan "
        "untuk tracking/notifikasi transaksi.\n\n"
        "Setelah bergabung, tekan <b>✅ Saya Sudah Bergabung</b>."
    )

    if update.callback_query:
        try:
            await update.callback_query.answer("Silakan bergabung dengan channel terlebih dahulu.", show_alert=True)
        except TelegramError:
            pass
        await update.callback_query.message.reply_text(
            text, parse_mode="HTML", reply_markup=membership_keyboard()
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            text, parse_mode="HTML", reply_markup=membership_keyboard()
        )
    return False
