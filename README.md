# TeleOrderBot

Telegram auto-order bot untuk penjualan produk digital dengan **QRIS DANA Bisnis manual**, kode unik 3 digit, manajemen stok, channel tracking pembayaran, verifikasi pembayaran oleh owner/admin, dan pengiriman produk otomatis setelah pembayaran dikonfirmasi.

> **Penting:** versi ini **tidak menggunakan QRIS otomatis, payment gateway, callback pembayaran, atau webhook QRIS**. QRIS berupa gambar statis DANA Bisnis. Customer membayar manual dan owner/admin mencocokkan transaksi berdasarkan nominal akhir + kode unik.

## Ringkasan alur

1. User membuka `/start`.
2. Bot memeriksa apakah user sudah menjadi member channel tracking yang dikonfigurasi pada `PAYMENT_CHANNEL_ID`.
3. Jika belum join, bot hanya menampilkan tombol **Gabung Channel** dan **Saya Sudah Bergabung**. User belum dapat membuka katalog atau melakukan order.
4. Setelah membership terverifikasi, user dapat melihat produk, memilih jumlah, dan membuat order.
5. Bot membuat kode unik random **100–400** dan menambahkannya ke subtotal. Contoh Rp5.000 + 214 = **Rp5.214**.
6. Bot mengirim QRIS DANA Bisnis statis dan nominal pembayaran yang harus dibayar tepat.
7. User menekan **Saya Sudah Bayar** dan mengirim screenshot bukti pembayaran.
8. Bukti diteruskan ke owner/admin dan channel tracking.
9. Owner/admin mencocokkan nominal di DANA Bisnis lalu menekan **Konfirmasi Pembayaran**.
10. Stok dikurangi secara atomik, order menjadi `PAID`, dan delivery text produk dikirim otomatis ke user.

---

# Fitur khusus Admin / Owner

Fitur berikut hanya dapat diakses oleh Telegram user ID yang sama dengan `ADMIN_USER_ID`.

| Fitur | Keterangan |
|---|---|
| `/admin` | Membuka Admin Panel. |
| Order terbaru | Menampilkan 10 order terbaru beserta status, customer ID, produk, subtotal, kode unik, dan total bayar. |
| Produk & stok | Menampilkan seluruh produk termasuk yang stoknya habis. |
| `/admin_products` | Menampilkan semua produk lengkap dengan ID, harga, stok, dan status. |
| `/admin_delete_product PRODUCT_ID` | Menghapus produk dari MongoDB setelah konfirmasi inline. |
| `/admin_add_product` | Membuat produk baru melalui percakapan interaktif. |
| `/admin_set_stock PRODUCT_ID JUMLAH` | Mengubah stok produk tertentu. |
| Notifikasi order baru | Owner menerima detail order baru secara private. |
| Bukti pembayaran | Screenshot user diteruskan ke private chat owner/admin. |
| Tracking channel | Claim pembayaran, screenshot bukti, dan pembayaran terverifikasi dikirim ke channel. |
| Mention owner | Channel dapat mention `OWNER_MENTION_USERNAME` atau fallback ke numeric owner ID. |
| Konfirmasi pembayaran | Tombol `✅ Konfirmasi Pembayaran` hanya berfungsi untuk admin. |
| Batalkan order | Tombol `❌ Batalkan` hanya berfungsi untuk admin. |
| Atomic stock deduction | Stok baru dikurangi ketika pembayaran dikonfirmasi, bukan saat order dibuat. |
| Auto delivery | Setelah status menjadi `PAID`, delivery text produk otomatis dikirim ke customer. |
| Proteksi stok negatif | Konfirmasi ditolak jika stok sudah tidak mencukupi. |
| Audit nominal | Owner dapat melihat kode unik dan total final untuk mencocokkan transaksi DANA. |

### Command admin

```text
/admin
/admin_add_product
/admin_set_stock PRODUCT_ID JUMLAH
/admin_products
/admin_delete_product PRODUCT_ID
```

Contoh:

```text
/admin_set_stock 3 25
/admin_products
/admin_delete_product 3
```

`/admin_delete_product` tidak langsung menghapus. Bot akan menampilkan tombol konfirmasi **🗑 Ya, Hapus** atau **Batal**. Bot menolak penghapusan jika produk masih memiliki order `PENDING`. Setelah tidak ada order pending, produk dapat dihapus; riwayat order lama tetap tersimpan karena order menyimpan snapshot nama produk, harga, quantity, dan nominal transaksi.

Saat `/admin_add_product`, bot meminta:

```text
1. Nama produk
2. Deskripsi
3. Harga satuan
4. Stok awal
5. Delivery text / isi produk
```

`delivery_text` adalah payload yang dikirim otomatis setelah owner mengonfirmasi pembayaran.

> Saat ini satu produk menggunakan satu `delivery_text` reusable. Project ini belum menggunakan pool credential unik per unit stok.

---

# Fitur User / Customer

Fitur customer hanya dapat digunakan **setelah membership channel wajib berhasil diverifikasi**.

| Fitur | Keterangan |
|---|---|
| `/start` | Memulai bot dan menjalankan pengecekan membership channel. |
| Wajib join channel | User non-admin tidak dapat masuk ke katalog sebelum menjadi member channel tracking. |
| Cek membership | Tombol `✅ Saya Sudah Bergabung` meminta bot mengecek membership secara langsung melalui Telegram. |
| Katalog produk | Menampilkan produk aktif yang masih memiliki stok. |
| Harga & stok | User melihat harga satuan dan stok tersedia sebelum membeli. |
| Pilih quantity | Jumlah pembelian dibatasi berdasarkan stok yang tersedia. |
| QRIS DANA Bisnis manual | Bot menampilkan gambar QRIS statis milik owner. |
| Kode unik 3 digit | Random 100–400 untuk membantu pencocokan pembayaran. |
| Total unik per order | Bot menghindari total pembayaran identik di antara order `PENDING`. |
| Saya Sudah Bayar | User dapat mengirim claim pembayaran ke owner/channel. |
| Upload screenshot | Screenshot bukti pembayaran disimpan sebagai Telegram `file_id` dan diteruskan ke owner/channel. |
| Status pembayaran | User menerima notifikasi ketika pembayaran dikonfirmasi atau order dibatalkan. |
| Auto delivery | Produk digital dikirim setelah admin mengonfirmasi pembayaran. |

User **tidak dapat** mengakses command admin, mengubah stok, membuat produk, mengonfirmasi pembayaran, atau membatalkan order milik customer lain.

---

# Membership channel wajib

Channel yang dipakai untuk tracking pembayaran juga digunakan sebagai **required channel**. User biasa harus join channel tersebut sebelum dapat memakai bot.

Konfigurasi:

```env
PAYMENT_CHANNEL_ID=-1001234567890
REQUIRED_CHANNEL_URL=https://t.me/nama_channel
REQUIRED_CHANNEL_NAME=Channel Transaksi
```

Untuk private channel gunakan invite link, misalnya:

```env
REQUIRED_CHANNEL_URL=https://t.me/+INVITE_CODE
```

### Syarat penting

Bot harus ditambahkan sebagai **admin channel**. Ini diperlukan agar bot dapat:

- mengirim notifikasi transaksi ke channel;
- mengirim screenshot bukti pembayaran;
- mengecek status membership user melalui Telegram `getChatMember`.

Owner/admin (`ADMIN_USER_ID`) dikecualikan dari membership gate agar panel admin tidak terkunci.

Jika pengecekan membership gagal karena konfigurasi channel/permission salah, akses customer akan ditolak (fail closed) dan error dicatat ke log.

---

# QRIS DANA Bisnis manual

Simpan QRIS statis sebagai:

```text
data/dana_business_qris.png
```

Konfigurasi:

```env
DANA_BUSINESS_NAME=Nama Bisnis Anda
DANA_BUSINESS_QRIS_IMAGE=./data/dana_business_qris.png
```

QRIS tidak dibuat oleh API. Tidak ada endpoint callback dari DANA/KlikQRIS/payment gateway. Pembayaran selalu diverifikasi manual oleh owner.

---

# Kode unik 3 digit

Default:

```env
UNIQUE_CODE_MIN=100
UNIQUE_CODE_MAX=400
```

Contoh:

| Subtotal | Kode | Total bayar |
|---:|---:|---:|
| Rp5.000 | 214 | Rp5.214 |
| Rp10.000 | 321 | Rp10.321 |
| Rp25.000 | 387 | Rp25.387 |

Kode dibuat baru setiap checkout dengan `secrets.randbelow()`. Kode bukan counter global. Nilai kode tetap disimpan pada record order agar owner dapat melakukan rekonsiliasi transaksi.

Bot juga mengecek order `PENDING` untuk menghindari dua order aktif memiliki `total_amount` yang sama.

---

# Status order

| Status | Arti |
|---|---|
| `PENDING` | Order dibuat dan menunggu pembayaran/verifikasi owner. |
| `PAID` | Owner sudah mengonfirmasi pembayaran. |
| `CANCELLED` | Order dibatalkan owner. |

Stok **tidak** dikurangi saat order dibuat. Stok dikurangi saat owner menekan **Konfirmasi Pembayaran**.

---

# Konfigurasi `config.env`

Copy template:

```bash
cp config-sample.env config.env
nano config.env
```

Contoh:

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
ADMIN_USER_ID=123456789

# Channel tracking + channel wajib join
PAYMENT_CHANNEL_ID=-1001234567890
REQUIRED_CHANNEL_URL=https://t.me/nama_channel
REQUIRED_CHANNEL_NAME=Channel Transaksi
OWNER_MENTION_USERNAME=your_username
OWNER_MENTION_LABEL=Owner

# QRIS manual DANA Bisnis
DANA_BUSINESS_NAME=Nama Bisnis Anda
DANA_BUSINESS_QRIS_IMAGE=./data/dana_business_qris.png

# Kode unik
UNIQUE_CODE_MIN=100
UNIQUE_CODE_MAX=400

# MongoDB
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DATABASE=teleorderbot

# Health endpoint lokal
HOST=0.0.0.0
PORT=8080
APP_PORT=8080

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/bot.log
```

Jangan commit file berikut ke public repository:

```text
config.env
.env
data/dana_business_qris.png
logs/
```

---

# MongoDB dan persistence data

Semua data operasional bot sekarang disimpan di **MongoDB**: produk, stok, user, dan order. Docker Compose menjalankan service `mongodb` menggunakan image `mongo:8.0` dan named volume:

```text
teleorderbot_mongodb_data
```

Named volume ini membuat data tetap ada saat:

- container bot restart;
- container MongoDB restart;
- `docker compose up -d --build`;
- source code di-update lalu redeploy;
- `docker compose down` biasa.

> **Jangan gunakan `docker compose down -v`** kecuali memang ingin menghapus database. Opsi `-v` akan menghapus named volume MongoDB.

Konfigurasi default:

```env
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DATABASE=teleorderbot
```

Saat upgrade dari versi SQLite lama, jika MongoDB masih kosong dan file `data/orders.db` masih tersedia, bot mencoba mengimpor tabel **products** lama satu kali ke MongoDB dengan ID produk yang sama. Setelah berhasil, produk berikutnya akan memakai ID lanjutan.

### Backup MongoDB

Buat backup:

```bash
mkdir -p backups
sudo docker exec teleorderbot-mongodb \
  mongodump --db teleorderbot --archive=/tmp/teleorderbot.archive --gzip
sudo docker cp teleorderbot-mongodb:/tmp/teleorderbot.archive \
  backups/teleorderbot-$(date +%Y%m%d-%H%M%S).archive
```

Untuk keamanan tambahan di luar VPS, copy file backup tersebut ke storage lain secara berkala.

---

# Docker

Versi ini menggunakan **Telegram long polling**. Port `8080` hanya untuk local health check dan **bukan** webhook pembayaran/QRIS.

Docker Compose menjalankan dua service:

```text
teleorderbot  -> aplikasi Telegram bot
mongodb       -> database MongoDB
```

Container utamanya:

```text
teleorderbot
teleorderbot-mongodb
```

### Build & start

```bash
mkdir -p data logs
sudo chown -R 10001:10001 data logs
sudo docker compose up -d --build
```

Cek:

```bash
sudo docker compose ps
sudo docker compose logs -f teleorderbot
sudo docker compose logs -f mongodb
curl http://127.0.0.1:8080/health
```

Restart:

```bash
sudo docker compose restart teleorderbot
# restart database bila memang diperlukan:
# sudo docker compose restart mongodb
```

Stop/start:

```bash
sudo docker compose stop teleorderbot
sudo docker compose start teleorderbot
```

Update source dari GitHub:

```bash
cd /opt/teleorderbot
git pull --ff-only
sudo docker compose up -d --build
```

---

# Deployment Ubuntu 24.04

Clone:

```bash
cd /opt
git clone https://github.com/vishnoe115/teleorderbot.git
cd teleorderbot
```

Buat config:

```bash
cp config-sample.env config.env
nano config.env
```

Upload QRIS ke:

```text
/opt/teleorderbot/data/dana_business_qris.png
```

Siapkan permission dan jalankan:

```bash
mkdir -p data logs
sudo chown -R 10001:10001 data logs
sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs -f teleorderbot
```

Health check:

```bash
curl http://127.0.0.1:8080/health
```

---

# Struktur project

```text
teleorderbot/
├── bot.py
├── config.py
├── db.py
├── logging_config.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── config-sample.env
├── .env.example
├── handlers/
│   ├── admin.py
│   ├── common.py
│   └── user.py
├── services/
│   ├── channel_notifications.py
│   ├── membership.py
│   └── orders.py
├── web/
│   └── app.py
├── data/                    # QRIS + legacy SQLite import source
└── tests/
```

---

# Checklist sebelum production

- `BOT_TOKEN` valid.
- `ADMIN_USER_ID` adalah numeric Telegram user ID owner.
- `PAYMENT_CHANNEL_ID` mengarah ke channel tracking yang benar.
- `REQUIRED_CHANNEL_URL` dapat dibuka user.
- Bot sudah menjadi admin channel tracking.
- Bot memiliki izin post message/media di channel.
- Membership check berhasil untuk akun member dan menolak akun non-member.
- QRIS statis sudah ada di `data/dana_business_qris.png`.
- `config.env`, log, QRIS, dan file backup database tidak masuk GitHub.
- Service MongoDB sehat dan named volume `teleorderbot_mongodb_data` tersedia.
- Jangan memakai `docker compose down -v` untuk update biasa.
- `data/` dan `logs/` writable oleh UID `10001` pada Docker.
- Owner sudah menguji flow order dari awal sampai auto delivery.

## Catatan keamanan

Bot tidak login ke akun DANA, tidak membaca OTP, tidak scraping histori DANA, dan tidak menganggap pembayaran berhasil secara otomatis. Status `PAID` hanya terjadi setelah owner/admin menekan tombol konfirmasi.
