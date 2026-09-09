# Runtime data directory

Folder ini digunakan untuk file QRIS statis dan kompatibilitas migrasi dari versi lama.

- `dana_business_qris.png` — QRIS DANA Bisnis milik owner. Jangan commit ke repository public.
- `orders.db` — hanya diperlukan sebagai sumber migrasi produk dari versi SQLite lama. Database utama sekarang MongoDB.

Data MongoDB tidak disimpan di folder ini. Docker Compose menyimpannya pada named volume `teleorderbot_mongodb_data`.
