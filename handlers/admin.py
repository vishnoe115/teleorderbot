from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

import db
from handlers.common import admin_keyboard, is_admin, order_text
from services.channel_notifications import post_payment_verified
from services.orders import rupiah

log = logging.getLogger(__name__)

ADD_NAME, ADD_DESC, ADD_PRICE, ADD_STOCK, ADD_DELIVERY = range(10, 15)


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return

    await update.effective_message.reply_text(
        "🔐 Admin Panel",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🧾 Order Terbaru", callback_data="a:orders")],
                [InlineKeyboardButton("📦 Produk & Stok", callback_data="a:products")],
            ]
        ),
    )


async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    rows = db.recent(10)
    if not rows:
        await query.message.reply_text("Belum ada order.")
        return

    for row in rows:
        await query.message.reply_text(
            order_text(row),
            parse_mode="HTML",
            reply_markup=admin_keyboard(row["order_id"]) if row["status"] == "PENDING" else None,
        )


async def products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    rows = db.products(active_only=False)
    text = "\n".join(
        f"#{item['id']} {item['name']} — {rupiah(item['price'])} — stok {item['stock']}"
        for item in rows
    )
    await query.message.reply_text(
        (text or "Produk kosong.")
        + "\n\nTambah produk: /admin_add_product\n"
        + "Ubah stok: /admin_set_stock PRODUCT_ID JUMLAH"
    )


async def mark_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    order_id = query.data.split(":", 2)[2]
    before = db.order(order_id)
    if not before:
        await query.message.reply_text("Order tidak ditemukan.")
        return

    success, reason = db.confirm_paid_and_take_stock(order_id)
    await query.edit_message_reply_markup(reply_markup=None)

    if not success:
        if reason == "INSUFFICIENT_STOCK":
            await query.message.reply_text(
                "❌ Pembayaran belum dikonfirmasi karena stok produk tidak mencukupi."
            )
        else:
            current = db.order(order_id)
            await query.message.reply_text(
                f"Order tidak diubah. Status/reason: {reason}"
            )
        return

    order = db.order(order_id)
    product = db.product(order["product_id"])

    await query.message.reply_text(
        f"✅ Pembayaran dikonfirmasi. Stok otomatis berkurang {order['quantity']}."
    )

    # Notify channel first, but do not block delivery if channel fails.
    try:
        await post_payment_verified(
            context.bot,
            order,
            source="QRIS DANA Bisnis - confirmed by admin",
        )
    except Exception:
        log.exception("Failed posting verified payment to channel")

    # Automatic delivery.
    delivery_text = (product["delivery_text"] or "").strip() if product else ""
    if delivery_text:
        if int(order["quantity"]) == 1:
            payload = delivery_text
        else:
            payload = (
                f"{delivery_text}\n\n"
                f"Jumlah pembelian: {order['quantity']} unit."
            )

        try:
            await context.bot.send_message(
                order["telegram_id"],
                f"✅ Pembayaran <b>{order_id}</b> terverifikasi.\n\n"
                f"📦 <b>Produk Anda:</b>\n{payload}",
                parse_mode="HTML",
            )
            db.mark_delivered(order_id)
            await query.message.reply_text("📦 Produk otomatis berhasil dikirim ke customer.")
        except Exception:
            log.exception("Automatic product delivery failed for %s", order_id)
            await query.message.reply_text(
                "⚠️ Pembayaran sudah PAID tetapi pengiriman otomatis gagal. Cek log bot."
            )
    else:
        await context.bot.send_message(
            order["telegram_id"],
            f"✅ Pembayaran <b>{order_id}</b> terverifikasi. "
            "Admin akan mengirim detail produk.",
            parse_mode="HTML",
        )
        await query.message.reply_text(
            "⚠️ Produk tidak memiliki delivery text, jadi tidak ada payload otomatis yang dikirim."
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    order_id = query.data.split(":", 2)[2]
    changed = db.cancel(order_id)
    order = db.order(order_id)
    await query.edit_message_reply_markup(reply_markup=None)

    if not order:
        return

    if changed:
        await query.message.reply_text("❌ Order dibatalkan.")
        await context.bot.send_message(
            order["telegram_id"],
            f"❌ Order <b>{order_id}</b> dibatalkan.",
            parse_mode="HTML",
        )
    else:
        await query.message.reply_text(f"Order tidak dapat dibatalkan. Status: {order['status']}.")


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    context.user_data.clear()
    await update.effective_message.reply_text("Nama produk:")
    return ADD_NAME


async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_product_name"] = update.effective_message.text.strip()
    await update.effective_message.reply_text("Deskripsi produk:")
    return ADD_DESC


async def add_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_product_description"] = update.effective_message.text.strip()
    await update.effective_message.reply_text("Harga satuan (angka saja, contoh 5000):")
    return ADD_PRICE


async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        price = int(update.effective_message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("Harga tidak valid.")
        return ADD_PRICE

    context.user_data["new_product_price"] = price
    await update.effective_message.reply_text("Jumlah stok awal (angka 0 atau lebih):")
    return ADD_STOCK


async def add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        stock = int(update.effective_message.text.strip())
        if stock < 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("Stok tidak valid.")
        return ADD_STOCK

    context.user_data["new_product_stock"] = stock
    await update.effective_message.reply_text(
        "Isi produk yang akan otomatis dikirim setelah pembayaran dikonfirmasi.\n\n"
        "Contoh:\n"
        "Email: akun@example.com\n"
        "Password: password123\n\n"
        "Pesan ini akan dikirim ke customer setelah admin menekan Konfirmasi Pembayaran."
    )
    return ADD_DELIVERY


async def add_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    delivery = update.effective_message.text.strip()

    product_id = db.add_product(
        context.user_data["new_product_name"],
        context.user_data["new_product_description"],
        context.user_data["new_product_price"],
        context.user_data["new_product_stock"],
        delivery,
    )

    await update.effective_message.reply_text(
        f"✅ Produk #{product_id} berhasil dibuat.\n"
        f"Stok: {context.user_data['new_product_stock']}\n"
        "Pengiriman otomatis: aktif."
    )
    context.user_data.clear()
    return ConversationHandler.END


async def set_stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) != 2:
        await update.effective_message.reply_text(
            "Format: /admin_set_stock PRODUCT_ID JUMLAH\n"
            "Contoh: /admin_set_stock 3 25"
        )
        return

    try:
        product_id = int(context.args[0])
        stock = int(context.args[1])
        if product_id <= 0 or stock < 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("Product ID atau stok tidak valid.")
        return

    if not db.set_stock(product_id, stock):
        await update.effective_message.reply_text("Produk tidak ditemukan.")
        return

    await update.effective_message.reply_text(
        f"✅ Stok produk #{product_id} diubah menjadi {stock}."
    )
