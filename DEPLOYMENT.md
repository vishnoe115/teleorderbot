# Deployment Reference — Ubuntu 24.04

Panduan deployment utama berada di [README.md](README.md).

Command inti setelah Docker Engine tersedia:

```bash
cd /opt
git clone https://github.com/USERNAME/REPOSITORY.git autoordertele
cd autoordertele

cp config-sample.env config.env
nano config.env

mkdir -p data logs
# Upload QRIS to data/dana_business_qris.png

sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs --tail=100 autoordertele
curl http://127.0.0.1:8080/health
```

Update:

```bash
cd /opt/autoordertele
cp data/orders.db data/orders.db.backup
git pull --ff-only
sudo docker compose up -d --build
```
