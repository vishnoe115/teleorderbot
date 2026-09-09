# AutoOrderTele

**Telegram Auto Order Bot — QRIS DANA Bisnis, Stock Management, Payment Proof Channel, dan Automatic Product Delivery**

AutoOrderTele adalah bot Telegram berbasis Python untuk penjualan produk digital. Customer dapat memilih produk, menentukan jumlah pembelian, membayar melalui **QRIS DANA Bisnis** dengan **kode unik 3 digit**, lalu mengirim bukti pembayaran. Admin memverifikasi pembayaran melalui tombol Telegram; setelah pembayaran dikonfirmasi, stok otomatis berkurang dan isi produk otomatis dikirim ke customer.

Project ini sudah disiapkan untuk deployment menggunakan **Docker Compose** pada VPS Ubuntu 24.04.

---

## Fitur Utama

### Customer

- Katalog produk langsung dari Telegram.
- Menampilkan harga dan stok yang masih tersedia.
- Pemilihan jumlah pembelian berdasarkan stok.
- Pembayaran manual menggunakan **QRIS DANA Bisnis**.
- Kode unik **3 digit** otomatis pada setiap order.
- Total pembayaran dibuat menjadi nominal unik untuk mempermudah pencocokan transaksi.
- Tombol **Saya Sudah Bayar**.
- Upload screenshot bukti pembayaran.
- Bukti pembayaran otomatis diteruskan ke admin dan channel transaksi.
- Customer menerima notifikasi setelah pembayaran dikonfirmasi.
- Produk digital otomatis dikirim setelah admin mengonfirmasi pembayaran.

### Admin / Owner

- Admin panel Telegram.
- Melihat order terbaru.
- Menambah produk baru langsung dari Telegram.
- Menentukan:
  - nama produk;
  - deskripsi;
  - harga;
  - jumlah stok;
  - isi produk yang akan dikirim otomatis.
- Melihat daftar produk dan stok.
- Mengubah stok produk melalui command.
- Menerima notifikasi order baru.
- Menerima screenshot bukti pembayaran.
- Tombol **Konfirmasi Pembayaran**.
- Tombol **Batalkan Order**.
- Stok berkurang otomatis ketika pembayaran berhasil dikonfirmasi.
- Isi produk otomatis dikirim ke customer.
- Payment log otomatis masuk ke channel transaksi.
- Owner/admin dapat di-mention pada channel transaksi.

### Backend

- Python 3.12.
- `python-telegram-bot`.
- SQLite dengan WAL mode.
- Database persisten melalui Docker volume.
- Atomic stock deduction ketika pembayaran dikonfirmasi.
- Migration database otomatis untuk versi lama.
- Rotating application logs.
- FastAPI health endpoint.
- Dockerfile non-root user.
- Docker Compose.
- Container health check.
- Restart container otomatis dengan `restart: unless-stopped`.

---

# Alur Transaksi

Contoh produk:

```text
Nama   : Premium Account
Harga  : Rp5.000
Stok   : 20
```

Customer membeli 1 produk.

Bot membuat kode unik, misalnya:

```text
Harga produk : Rp5.000
Kode unik    : 214
Total bayar  : Rp5.214
```

Customer akan menerima QRIS dan instruksi:

```text
🧾 INV-123456789-...

📦 Premium Account x1

💵 Subtotal: Rp5.000
🔢 Kode unik: 214
💰 TOTAL BAYAR: Rp5.214

🏪 QRIS DANA Bisnis: Nama Bisnis Anda

Silakan scan QRIS dan bayar TEPAT Rp5.214.
```

Setelah membayar:

1. Customer mengirim screenshot bukti pembayaran.
2. Screenshot otomatis masuk ke private chat admin dan channel transaksi.
3. Owner/admin otomatis di-mention di channel.
4. Admin mencocokkan nominal pembayaran pada DANA Bisnis.
5. Admin menekan **✅ Konfirmasi Pembayaran**.
6. Database memastikan stok masih tersedia.
7. Stok otomatis dikurangi.
8. Order berubah dari `PENDING` menjadi `PAID`.
9. Isi produk otomatis dikirim ke customer.
10. Channel transaksi menerima notifikasi pembayaran terverifikasi.

> Verifikasi pembayaran tetap dilakukan oleh admin. Bot tidak melakukan login, scraping, membaca OTP, atau mengambil histori transaksi akun DANA secara otomatis.

---

# Kode Unik 3 Digit

Kode tracking dibuat dengan `secrets.randbelow()` **setiap kali order baru dibuat**. Nilainya tidak disimpan sebagai konfigurasi tetap/global dan tidak dipakai ulang sebagai urutan counter.

Bot tetap menyimpan kode tersebut pada **record order yang bersangkutan** karena owner perlu mengetahui nominal yang harus dicocokkan. Selain itu, bot menghindari penggunaan `total_amount` yang sama pada dua order `PENDING` secara bersamaan.

Contoh:

```text
Harga item : Rp5.000
Kode       : 214
Total      : Rp5.214
```

Order berikutnya dapat memperoleh nilai lain, misalnya:

```text
Harga item : Rp5.000
Kode       : 321
Total      : Rp5.321
```

Kode dibatasi maksimal **Rp400**.


Kode unik default:

```env
UNIQUE_CODE_MIN=100
UNIQUE_CODE_MAX=400
```

Contoh:

| Harga | Kode | Total bayar |
|---:|---:|---:|
| Rp5.000 | 214 | Rp5.214 |
| Rp10.000 | 321 | Rp10.321 |
| Rp25.000 | 387 | Rp25.387 |

Kode unik sudah termasuk di dalam **total yang harus dibayar customer**.

---

# Command Bot

## Command Customer

| Command | Fungsi |
|---|---|
| `/start` | Membuka bot dan menampilkan tombol katalog produk. |

Pembelian selanjutnya dilakukan melalui tombol inline Telegram:

```text
🛍️ Lihat Produk
→ Pilih Produk
→ Masukkan Jumlah
→ Bayar QRIS DANA Bisnis
→ Saya Sudah Bayar
→ Upload Bukti
```

## Command Admin

Admin dikenali berdasarkan:

```env
ADMIN_USER_ID=123456789
```

### `/admin`

Membuka admin panel.

Menu:

```text
🧾 Order Terbaru
📦 Produk & Stok
```

### `/admin_add_product`

Menambahkan produk baru.

Bot akan meminta:

```text
1. Nama produk
2. Deskripsi produk
3. Harga
4. Jumlah stok
5. Isi produk / delivery text
```

Contoh:

```text
Nama:
Netflix Premium

Deskripsi:
Akun premium 30 hari

Harga:
50000

Stok:
10

Delivery:
Email: example@email.com
Password: password123
```

`Delivery` akan otomatis dikirim kepada customer setelah admin mengonfirmasi pembayaran.

### `/admin_set_stock PRODUCT_ID JUMLAH`

Mengubah jumlah stok.

Contoh:

```text
/admin_set_stock 3 25
```

Artinya stok produk ID `3` menjadi `25`.

Untuk melihat Product ID:

```text
/admin
→ 📦 Produk & Stok
```

---

# Status Order

Status utama:

| Status | Arti |
|---|---|
| `PENDING` | Order dibuat dan menunggu pembayaran/verifikasi. |
| `PAID` | Pembayaran sudah dikonfirmasi admin. |
| `CANCELLED` | Order dibatalkan. |

Stok **tidak dikurangi ketika order dibuat**.

Stok baru dikurangi pada saat admin menekan:

```text
✅ Konfirmasi Pembayaran
```

Sebelum mengurangi stok, bot melakukan pengecekan ulang secara atomik agar stok tidak menjadi negatif.

---

# Payment Proof Channel

Bot dapat mengirim semua bukti pembayaran ke channel Telegram khusus.

Contoh konfigurasi:

```env
PAYMENT_CHANNEL_ID=-1001234567890
OWNER_MENTION_USERNAME=username_owner
OWNER_MENTION_LABEL=Owner
```

Tambahkan bot sebagai admin/member channel dan berikan izin:

```text
Post Messages
```

Screenshot customer diteruskan menggunakan Telegram `file_id`, jadi bot tidak perlu download lalu menyimpan screenshot pembayaran ke VPS.

---

# Struktur Repository

```text
autoordertele/
├── bot.py
├── config.py
├── db.py
├── logging_config.py
├── requirements.txt
│
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .gitignore
├── config-sample.env
├── .env.example
│
├── handlers/
│   ├── __init__.py
│   ├── common.py
│   ├── user.py
│   └── admin.py
│
├── services/
│   ├── __init__.py
│   ├── channel_notifications.py
│   └── orders.py
│
├── web/
│   ├── __init__.py
│   └── app.py
│
├── data/
│   ├── README.md
│   └── seed_products.json
│
├── tests/
│   └── test_helpers.py
│
├── check_install.py
├── MIGRATION.md
└── README.md
```

---

# Configuration

Copy:

```bash
cp config-sample.env config.env
```

Kemudian edit:

```bash
nano config.env
```

Contoh lengkap:

```env
# Telegram
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
ADMIN_USER_ID=123456789

# Channel transaksi
PAYMENT_CHANNEL_ID=-1001234567890
OWNER_MENTION_USERNAME=username_owner
OWNER_MENTION_LABEL=Owner

# QRIS DANA Bisnis
DANA_BUSINESS_NAME=Nama Bisnis Anda
DANA_BUSINESS_QRIS_IMAGE=./data/dana_business_qris.png

# Kode unik tiga digit
UNIQUE_CODE_MIN=100
UNIQUE_CODE_MAX=400

# Database
DB_PATH=./data/orders.db

# Internal HTTP server
HOST=0.0.0.0
PORT=8080

# Port pada VPS
APP_PORT=8080

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/bot.log
```

Jangan commit:

```text
config.env
.env
data/orders.db
data/dana_business_qris.png
logs/
```

File tersebut sudah dimasukkan ke `.gitignore`.

---

# Mendapatkan Telegram Bot Token

1. Buka Telegram.
2. Cari `@BotFather`.
3. Jalankan `/newbot`.
4. Ikuti instruksi BotFather.
5. Copy token ke:

```env
BOT_TOKEN=...
```

Jangan pernah membagikan token bot ke repository publik.

---

# Mendapatkan ADMIN_USER_ID

Gunakan bot seperti `@userinfobot` atau metode lain yang menampilkan numeric Telegram user ID.

Contoh:

```env
ADMIN_USER_ID=123456789
```

Gunakan **numeric ID**, bukan username.

---

# Menyiapkan QRIS DANA Bisnis

Simpan gambar QRIS bisnis sebagai:

```text
data/dana_business_qris.png
```

Kemudian:

```env
DANA_BUSINESS_QRIS_IMAGE=./data/dana_business_qris.png
```

QRIS image tidak ikut GitHub karena dikecualikan oleh `.gitignore`.

Upload QRIS langsung ke VPS setelah repository di-clone.

---

# Membuat Repository GitHub Baru

Buat repository baru di GitHub, misalnya:

```text
telegram-auto-order
```

Sebaiknya pilih:

```text
Do not initialize with README
Do not initialize with .gitignore
Do not initialize with license
```

karena project ini sudah mempunyai file tersebut.

Extract ZIP project ke komputer Anda lalu buka terminal pada directory project.

```bash
git init
git add .
git commit -m "Initial AutoOrderTele release"
git branch -M main
```

Tambahkan repository GitHub:

```bash
git remote add origin https://github.com/USERNAME/REPOSITORY.git
```

Contoh:

```bash
git remote add origin https://github.com/vishnoe115/telegram-auto-order.git
```

Push:

```bash
git push -u origin main
```

Untuk memastikan remote:

```bash
git remote -v
```

---

# Deployment VPS Ubuntu 24.04

## 1. Login ke VPS

```bash
ssh root@IP_VPS
```

atau user sudo:

```bash
ssh username@IP_VPS
```

---

## 2. Update Ubuntu

```bash
sudo apt update
sudo apt upgrade -y
```

Install tools dasar:

```bash
sudo apt install -y ca-certificates curl git
```

---

## 3. Install Docker Engine

Hapus package Docker yang mungkin bentrok:

```bash
sudo apt remove -y docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc || true
```

Tambahkan official Docker GPG key:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

Tambahkan repository Docker:

```bash
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

Update:

```bash
sudo apt update
```

Install Docker Engine + Compose:

```bash
sudo apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin
```

Enable Docker:

```bash
sudo systemctl enable --now docker
```

Verifikasi:

```bash
sudo docker run --rm hello-world
```

Cek Compose:

```bash
sudo docker compose version
```

---

## 4. Clone Repository

Contoh:

```bash
cd /opt
sudo git clone https://github.com/USERNAME/REPOSITORY.git autoordertele
cd autoordertele
```

Jika menggunakan root:

```bash
cd /opt
git clone https://github.com/USERNAME/REPOSITORY.git autoordertele
cd autoordertele
```

---

## 5. Buat Configuration

```bash
cp config-sample.env config.env
nano config.env
```

Isi credential Anda.

Minimal:

```env
BOT_TOKEN=TOKEN_BOT
ADMIN_USER_ID=123456789

PAYMENT_CHANNEL_ID=-1001234567890
OWNER_MENTION_USERNAME=username_owner
OWNER_MENTION_LABEL=Owner

DANA_BUSINESS_NAME=Nama Bisnis
DANA_BUSINESS_QRIS_IMAGE=./data/dana_business_qris.png

UNIQUE_CODE_MIN=100
UNIQUE_CODE_MAX=400
```

---

## 6. Upload Gambar QRIS

Dari komputer lokal:

```bash
scp dana_business_qris.png \
  root@IP_VPS:/opt/autoordertele/data/dana_business_qris.png
```

Atau upload menggunakan SFTP/WinSCP ke:

```text
/opt/autoordertele/data/dana_business_qris.png
```

Pastikan file ada:

```bash
ls -lah data/dana_business_qris.png
```

---

## 7. Buat Runtime Directory

```bash
mkdir -p data logs
```

Jika permission Docker bermasalah:

```bash
sudo chown -R 10001:10001 data logs
```

---

## 8. Build dan Jalankan Bot

```bash
sudo docker compose up -d --build
```

Cek:

```bash
sudo docker compose ps
```

Status ideal:

```text
Up ... (healthy)
```

---

## 9. Cek Log

```bash
sudo docker compose logs -f autoordertele
```

Keluar dari log:

```text
Ctrl + C
```

Container tetap berjalan.

---

## 10. Health Check

```bash
curl http://127.0.0.1:8080/health
```

Response:

```json
{
  "ok": true,
  "database": "ok",
  "payment": "DANA_BUSINESS_QRIS"
}
```

---

# Setelah Deploy

Buka Telegram lalu jalankan:

```text
/start
```

Untuk admin:

```text
/admin
```

Tambahkan produk pertama:

```text
/admin_add_product
```

Setelah produk dibuat:

```text
/start
→ Lihat Produk
```

Lakukan transaksi test sebelum membuka bot untuk customer.

---

# Update Bot dari GitHub

Setelah Anda push perubahan baru ke GitHub:

```bash
cd /opt/autoordertele
```

Backup database:

```bash
cp data/orders.db data/orders.db.backup
```

Pull source:

```bash
git pull --ff-only
```

Rebuild:

```bash
sudo docker compose up -d --build
```

Cek:

```bash
sudo docker compose ps
sudo docker compose logs --tail=100 autoordertele
```

Tidak perlu menjalankan `docker compose down` untuk update normal.

---

# Restart Bot

```bash
sudo docker compose restart autoordertele
```

---

# Stop Bot

```bash
sudo docker compose down
```

Database tidak terhapus karena disimpan di:

```text
./data/orders.db
```

---

# Start Kembali

```bash
sudo docker compose up -d
```

---

# Rebuild dari Nol

```bash
sudo docker compose down
sudo docker compose build --no-cache
sudo docker compose up -d
```

---

# Backup Database

Manual:

```bash
cp data/orders.db \
  "data/orders-backup-$(date +%Y%m%d-%H%M%S).db"
```

Melihat backup:

```bash
ls -lh data/*.db
```

Sebaiknya backup database secara rutin karena database menyimpan produk, stok, user, dan order.

---

# Restore Database

Stop container:

```bash
sudo docker compose down
```

Restore:

```bash
cp data/orders-backup-YYYYMMDD-HHMMSS.db data/orders.db
```

Start:

```bash
sudo docker compose up -d
```

---

# Log Application

File log:

```text
logs/bot.log
```

Lihat:

```bash
tail -f logs/bot.log
```

atau melalui Docker:

```bash
sudo docker compose logs -f autoordertele
```

---

# Troubleshooting

## Bot tidak merespons

Cek container:

```bash
sudo docker compose ps
```

Cek log:

```bash
sudo docker compose logs --tail=200 autoordertele
```

Pastikan:

```env
BOT_TOKEN=...
ADMIN_USER_ID=...
```

benar.

---

## Container terus restart

Jalankan:

```bash
sudo docker compose logs --tail=200 autoordertele
```

Penyebab umum:

- `BOT_TOKEN` salah/kosong;
- `ADMIN_USER_ID` bukan angka;
- `DANA_BUSINESS_NAME` kosong;
- permission `data/` atau `logs/`.

---

## QRIS tidak muncul

Pastikan:

```bash
ls -lah data/dana_business_qris.png
```

dan:

```env
DANA_BUSINESS_QRIS_IMAGE=./data/dana_business_qris.png
```

Kemudian restart:

```bash
sudo docker compose restart autoordertele
```

---

## Bukti pembayaran tidak masuk channel

Pastikan:

```env
PAYMENT_CHANNEL_ID=-100xxxxxxxxxx
```

Bot harus berada di channel dan mempunyai izin:

```text
Post Messages
```

Cek log:

```bash
sudo docker compose logs --tail=200 autoordertele
```

---

## Produk tidak muncul

Produk dengan stok `0` tidak tampil pada katalog customer.

Cek:

```text
/admin
→ Produk & Stok
```

Ubah stok:

```text
/admin_set_stock ID JUMLAH
```

Contoh:

```text
/admin_set_stock 1 10
```

---

## Produk tidak otomatis terkirim

Auto delivery hanya berjalan setelah admin menekan:

```text
✅ Konfirmasi Pembayaran
```

Pastikan produk mempunyai `delivery_text`.

Produk yang dibuat melalui:

```text
/admin_add_product
```

akan meminta delivery text pada langkah terakhir.

---

## Database lama

Saat startup, bot otomatis menambahkan field yang diperlukan:

```text
products.stock
products.delivery_text
orders.unique_code
orders.delivered_at
```

Tetap lakukan backup database sebelum upgrade.

---

# Security

Jangan pernah push:

```text
config.env
.env
data/orders.db
data/dana_business_qris.png
logs/
```

Jangan menyimpan:

- Telegram Bot Token;
- data login DANA;
- password akun pribadi;
- secret lain;

di repository GitHub publik.

Bot ini **tidak membutuhkan username/password/OTP akun DANA**.

---

# Production Checklist

Sebelum bot digunakan customer:

- [ ] `BOT_TOKEN` sudah benar.
- [ ] `ADMIN_USER_ID` sudah benar.
- [ ] Bot dapat merespons `/start`.
- [ ] `/admin` hanya dapat digunakan admin.
- [ ] Bot sudah ditambahkan ke payment channel.
- [ ] Bot mempunyai izin Post Messages.
- [ ] `PAYMENT_CHANNEL_ID` benar.
- [ ] QRIS DANA Bisnis sudah di-upload.
- [ ] Nama DANA Bisnis sudah benar.
- [ ] Kode unik berada pada range 100–400.
- [ ] Produk sudah dibuat.
- [ ] Stok produk sudah benar.
- [ ] Delivery text sudah diuji.
- [ ] Screenshot pembayaran masuk channel.
- [ ] Konfirmasi pembayaran mengurangi stok.
- [ ] Produk otomatis sampai ke customer.
- [ ] Database sudah dibackup.

---

# Quick Deploy

Untuk VPS yang Docker-nya sudah terpasang:

```bash
cd /opt

git clone https://github.com/USERNAME/REPOSITORY.git autoordertele
cd autoordertele

cp config-sample.env config.env
nano config.env

mkdir -p data logs

# Upload QRIS ke:
# data/dana_business_qris.png

sudo docker compose up -d --build

sudo docker compose ps
sudo docker compose logs --tail=100 autoordertele

curl http://127.0.0.1:8080/health
```

Kemudian test:

```text
/start
/admin
/admin_add_product
```

---

# License / Usage

Gunakan dan modifikasi project ini sesuai kebutuhan Anda. Jika repository akan dibuka untuk publik, tambahkan file `LICENSE` sesuai lisensi yang Anda pilih.

---

## Disclaimer

Bot ini membantu mengelola order, stok, bukti pembayaran, dan pengiriman produk digital. Verifikasi pembayaran QRIS DANA Bisnis pada versi ini tetap dilakukan oleh admin secara manual. Pastikan penggunaan QRIS, DANA Bisnis, produk yang dijual, dan proses transaksi mematuhi ketentuan layanan dan peraturan yang berlaku.
