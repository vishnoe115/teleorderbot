from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import ContextTypes, ConversationHandler

import db
from config import settings
from handlers.common import admin_keyboard, order_text
from services.channel_notifications import post_payment_claim, post_payment_proof
from services.orders import new_order_id, rupiah, random_unique_payment_code

log = logging.getLogger(__name__)

WAIT_QTY, WAIT_PAY = range(2)


async def notify_admin(context_or_app, order_id: str, extra: str = "") -> None:
    order = db.order(order_id)
    if not order:
        return

    text = order_text(order)
    if extra:
        text += f"\n\n{extra}"

    await context_or_app.bot.send_message(
        settings.admin_user_id,
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard(order_id),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db.upsert_user(update.effective_user)
    await update.effective_message.reply_text(
        "Selamat datang! 👋",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🛍️ Lihat Produk", callback_data="catalog")]]
        ),
    )


async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    items = db.products()
    if not items:
        await query.edit_message_text("Belum ada produk dengan stok tersedia.")
        return

    rows = [
        [
            InlineKeyboardButton(
                f"{item['name']} — {rupiah(item['price'])} | stok {item['stock']}",
                callback_data=f"p:{item['id']}",
            )
        ]
        for item in items
    ]

    await query.edit_message_text(
        "🛍️ <b>Pilih Produk</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split(":", 1)[1])
    item = db.product(product_id)

    if not item or not item["active"] or int(item["stock"]) <= 0:
        await query.edit_message_text("Produk sedang tidak tersedia.")
        return ConversationHandler.END

    context.user_data["product_id"] = item["id"]

    await query.edit_message_text(
        f"📦 <b>{item['name']}</b>\n"
        f"{item['description']}\n\n"
        f"Harga: <b>{rupiah(item['price'])}</b>\n"
        f"Stok tersedia: <b>{item['stock']}</b>\n\n"
        f"Kirim jumlah pembelian (1-{item['stock']}):",
        parse_mode="HTML",
    )
    return WAIT_QTY


async def receive_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    item = db.product(context.user_data.get("product_id", 0))
    if not item or not item["active"] or int(item["stock"]) <= 0:
        await update.effective_message.reply_text("Produk sudah tidak tersedia.")
        context.user_data.clear()
        return ConversationHandler.END

    try:
        quantity = int(update.effective_message.text.strip())
        if not 1 <= quantity <= min(100, int(item["stock"])):
            raise ValueError
    except (TypeError, ValueError):
        await update.effective_message.reply_text(
            f"Jumlah harus 1 sampai {min(100, int(item['stock']))}."
        )
        return WAIT_QTY

    base_amount = int(item["price"]) * quantity

    context.user_data["quantity"] = quantity
    context.user_data["amount"] = base_amount

    await update.effective_message.reply_text(
        f"{item['name']} x{quantity}\n"
        f"Total produk: <b>{rupiah(base_amount)}</b>\n\n"
        "Metode pembayaran:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔵 Bayar QRIS DANA Bisnis", callback_data="pay:qris")]]
        ),
    )
    return WAIT_PAY


async def choose_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    item = db.product(context.user_data.get("product_id", 0))
    quantity = context.user_data.get("quantity")
    base_amount = context.user_data.get("amount")

    if not item or not quantity or not base_amount:
        await query.message.reply_text("Sesi pembelian berakhir. Silakan /start lagi.")
        context.user_data.clear()
        return ConversationHandler.END

    if int(item["stock"]) < int(quantity):
        await query.message.reply_text(
            f"Maaf, stok berubah. Saat ini tersisa {item['stock']}."
        )
        context.user_data.clear()
        return ConversationHandler.END

    order_id = new_order_id(query.from_user.id)

    # Generate a fresh 3-digit code per order and avoid duplicate payable
    # totals among currently PENDING orders. This makes manual reconciliation
    # much easier for the owner.
    code = None
    total_amount = None
    for _ in range(50):
        candidate = random_unique_payment_code()
        candidate_total = int(base_amount) + candidate
        if not db.pending_total_exists(candidate_total):
            code = candidate
            total_amount = candidate_total
            break

    if code is None or total_amount is None:
        await query.message.reply_text(
            "Sedang terlalu banyak order dengan nominal serupa. Silakan coba lagi sebentar."
        )
        context.user_data.clear()
        return ConversationHandler.END

    try:
        db.create_order(
            order_id,
            query.from_user.id,
            item,
            int(quantity),
            int(base_amount),
            total_amount,
            code,
            "DANA_BUSINESS_QRIS",
        )
    except ValueError:
        await query.message.reply_text("Stok tidak mencukupi. Silakan pilih ulang produk.")
        context.user_data.clear()
        return ConversationHandler.END

    text = (
        f"🧾 <b>{order_id}</b>\n"
        f"📦 {item['name']} x{quantity}\n\n"
        f"💵 Subtotal: {rupiah(base_amount)}\n"
        f"🔢 Kode unik: <b>{code:03d}</b>\n"
        f"💰 <b>TOTAL BAYAR: {rupiah(total_amount)}</b>\n\n"
        f"🏪 QRIS DANA Bisnis: <b>{settings.dana_business_name}</b>\n\n"
        f"Silakan scan QRIS dan bayar <b>TEPAT {rupiah(total_amount)}</b>.\n"
        f"Tiga digit kode unik <b>{code:03d}</b> sudah dimasukkan ke total tagihan.\n\n"
        "Setelah membayar, kirim screenshot bukti pembayaran ke bot ini."
    )

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Saya Sudah Bayar", callback_data=f"dana_paid:{order_id}")]]
    )

    if settings.dana_business_qris_image.exists():
        with settings.dana_business_qris_image.open("rb") as fh:
            await query.message.reply_photo(
                InputFile(fh),
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
    else:
        await query.message.reply_text(
            text + "\n\n⚠️ Gambar QRIS DANA Bisnis belum dipasang oleh admin.",
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    await notify_admin(
        context,
        order_id,
        f"Menunggu pembayaran QRIS DANA Bisnis.\n"
        f"Kode unik: {code:03d}\n"
        f"Total cocokkan: {rupiah(total_amount)}",
    )

    context.user_data.clear()
    return ConversationHandler.END


async def dana_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    order_id = query.data.split(":", 1)[1]
    order = db.order(order_id)

    if not order or order["telegram_id"] != query.from_user.id:
        return

    if order["status"] != "PENDING":
        await query.message.reply_text(f"Status order: {order['status']}.")
        return

    await query.message.reply_text(
        "Notifikasi sudah dikirim ke admin. Kirim screenshot pembayaran untuk mempercepat verifikasi."
    )
    await notify_admin(
        context,
        order_id,
        "⚠️ Customer menekan Saya Sudah Bayar. Cocokkan nominal QRIS DANA Bisnis.",
    )
    await post_payment_claim(context.bot, order)


async def payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message.photo:
        return

    order = db.latest_pending_for_user(update.effective_user.id)
    if not order:
        await update.effective_message.reply_text(
            "Tidak ditemukan order pending untuk akun Anda."
        )
        return

    file_id = update.effective_message.photo[-1].file_id
    db.add_proof(order["order_id"], file_id)

    await update.effective_message.reply_text(
        "📎 Bukti pembayaran diterima dan diteruskan ke admin/channel transaksi."
    )

    try:
        await context.bot.send_photo(
            settings.admin_user_id,
            file_id,
            caption=f"Bukti pembayaran {order['order_id']}",
        )
    except Exception:
        log.exception("Failed to send proof to admin")

    await post_payment_proof(context.bot, order, file_id)
    await notify_admin(
        context,
        order["order_id"],
        "Ada bukti pembayaran baru. Cocokkan total QRIS lalu tekan Konfirmasi Pembayaran.",
    )
