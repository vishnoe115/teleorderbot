# Migrasi ke QRIS DANA Bisnis + Stock

## Backup

```bash
cp -a data data-backup
```

## Config baru

Hapus config DANA personal lama seperti:

```text
DANA_NUMBER
DANA_NAME
DANA_QRIS_IMAGE
DANA_UNIQUE_MIN
DANA_UNIQUE_MAX
```

Gunakan:

```env
DANA_BUSINESS_NAME=Nama Bisnis
DANA_BUSINESS_QRIS_IMAGE=./data/dana_business_qris.png
UNIQUE_CODE_MIN=100
UNIQUE_CODE_MAX=400
```

## Database

Schema akan menambahkan kolom berikut secara otomatis jika database lama dipakai:

```text
products.stock
products.delivery_text
orders.unique_code
orders.delivered_at
```

## Rebuild

```bash
docker compose down
docker compose up -d --build
docker compose logs -f autoordertele
```


## Kode unik tracking

Kode unik sekarang digenerate random 100-400 untuk setiap order. Nilainya disimpan hanya pada record order agar pembayaran dapat direkonsiliasi, dan bot menghindari total pembayaran identik di antara order PENDING.

## MongoDB migration

Versi ini menggunakan MongoDB sebagai database utama untuk produk, stok, user, dan order.

Default Docker Compose:

```env
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DATABASE=teleorderbot
```

MongoDB memakai named volume `teleorderbot_mongodb_data`, sehingga data tetap ada saat container restart, image rebuild, Git pull, dan redeployment normal.

Jika collection `products` MongoDB masih kosong dan file legacy `data/orders.db` tersedia, bot mencoba mengimpor produk lama dari SQLite satu kali dengan ID yang sama.

Jangan menjalankan `docker compose down -v` untuk update normal karena opsi `-v` menghapus volume database.
