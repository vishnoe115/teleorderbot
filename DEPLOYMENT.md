# Deployment Reference — Ubuntu 24.04

Panduan deployment utama berada di [README.md](README.md).

Command inti setelah Docker Engine tersedia:

```bash
cd /opt
git clone https://github.com/USERNAME/REPOSITORY.git teleorderbot
cd teleorderbot

cp config-sample.env config.env
nano config.env

mkdir -p data logs
# Upload QRIS to data/dana_business_qris.png

sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs --tail=100 teleorderbot
sudo docker compose logs --tail=100 mongodb
curl http://127.0.0.1:8080/health
```

Update:

```bash
cd /opt/teleorderbot
git pull --ff-only
sudo docker compose up -d --build
```


MongoDB persistence:

```bash
sudo docker volume ls | grep teleorderbot_mongodb_data
```

Volume tersebut tetap ada pada restart/redeploy dan `docker compose down` biasa. Jangan gunakan `docker compose down -v` untuk update normal karena `-v` menghapus volume database.

Backup MongoDB:

```bash
mkdir -p backups
sudo docker exec teleorderbot-mongodb \
  mongodump --db teleorderbot --archive=/tmp/teleorderbot.archive --gzip
sudo docker cp teleorderbot-mongodb:/tmp/teleorderbot.archive \
  backups/teleorderbot-$(date +%Y%m%d-%H%M%S).archive
```
