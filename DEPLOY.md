# Деплой на Google Cloud — команды и настройки

## Google Cloud VM

### Создание VM (через gcloud CLI)

UI не работал из-за удалённого service account — создавали через CLI.

```bash
# Установить gcloud CLI (macOS)
brew install google-cloud-sdk

# Авторизация и выбор проекта
gcloud init

# Создать service account (если удалён дефолтный)
# IAM & Admin → Service Accounts → Create
# Name: compute-default
# Role: Compute Engine default service account

# Создать VM
gcloud compute instances create psyai-vm \
  --project=YOUR_PROJECT_ID \
  --zone=us-central1-f \
  --machine-type=e2-medium \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-size=20GB \
  --tags=http-server,https-server
```

**Параметры VM:**
- Machine type: `e2-medium` (2 vCPU, 4 GB RAM)
- Zone: `us-central1-f` (us-central1-a — ZONE_RESOURCE_POOL_EXHAUSTED)
- OS: Debian 12
- Billing: Standard (не Spot — Spot может выключиться в любой момент)
- IP: `136.114.243.136`

---

## Firewall — открыть порты

```bash
# Открыть порт 8000 (FastAPI app)
gcloud compute firewall-rules create allow-8000 \
  --allow tcp:8000 \
  --source-ranges 0.0.0.0/0 \
  --description "Allow app port"

# Открыть порт 9000 (Portainer HTTP)
gcloud compute firewall-rules create allow-9000 \
  --allow tcp:9000 \
  --source-ranges 0.0.0.0/0 \
  --description "Allow Portainer HTTP"

# Открыть порт 9443 (Portainer HTTPS)
gcloud compute firewall-rules create allow-9443 \
  --allow tcp:9443 \
  --source-ranges 0.0.0.0/0 \
  --description "Allow Portainer HTTPS"
```

Или через UI: VPC network → Firewall → Create Firewall Rule.

---

## Подключение к VM

```bash
# SSH через gcloud
gcloud compute ssh psyai-vm --zone=us-central1-f

# Или напрямую (если есть SSH ключ)
ssh -i ~/.ssh/google_compute_engine username@136.114.243.136
```

---

## Установка Docker на VM

```bash
# Обновить пакеты
sudo apt-get update

# Установить зависимости
sudo apt-get install -y ca-certificates curl gnupg

# Добавить GPG ключ Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Добавить репозиторий
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установить Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Добавить пользователя в группу docker (чтобы не писать sudo)
sudo usermod -aG docker $USER
newgrp docker

# Проверить
docker --version
docker compose version
```

---

## Структура директорий на VM

```bash
# Создать директорию для проекта
sudo mkdir -p /opt/psyai
sudo chown $USER:$USER /opt/psyai
cd /opt/psyai

# Структура (Portainer создаёт сам при деплое)
/opt/psyai/
```

---

## Установка Portainer

```bash
# Создать volume для данных Portainer
docker volume create portainer_data

# Запустить Portainer CE
docker run -d \
  -p 9443:9443 \
  -p 9000:9000 \
  --name portainer \
  --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce:latest
```

**Portainer UI:** `http://136.114.243.136:9000`
Первый вход → создать admin пароль → выбрать Local environment.

---

## Деплой приложения через Portainer GitOps

**Stacks → Add stack → Repository**

| Поле | Значение |
|---|---|
| Name | `gestalt-supervisor` |
| Repository URL | `https://github.com/ivproduction/psyai-gestalt-supervisor` |
| Branch | `refs/heads/master` |
| Compose path | `docker-compose.yml` |
| Auto update | включить (каждые 5 минут) |

**Environment variables (Advanced mode):**
```
GEMINI_API_KEY=...
TELEGRAM_BOT_TOKEN=...
```

Остальные переменные берутся из дефолтов в `docker-compose.yml`.

---

## Загрузка книг в Qdrant (после деплоя)

Swagger UI: `http://136.114.243.136:8000/swagger`

### Вариант A — через API (конвертация на сервере)

```
1. POST /api/admin/files/upload       — загрузить PDF
2. POST /api/admin/files/convert      — PDF → Markdown (Gemini Vision, ~2-3 мин)
   ?filename=book.pdf&mode=smart&source_type=session_guides
3. POST /api/admin/files/ingest       — Markdown → Qdrant (эмбеддинги)
   ?filename=smart:book.txt&source_type=session_guides
4. GET  /api/admin/search             — проверить качество поиска
   ?query=сопротивление&source_type=session_guides&mode=smart
```

### Вариант B — загрузить готовые .txt файлы через SSH

Если конвертированные файлы уже есть локально в `data/docs/smart/` и `data/docs/standard/`:

```bash
# 1. Закинуть файлы на VM
scp -i ~/.ssh/google_compute_engine \
  data/docs/smart/book.txt \
  data/docs/smart/book.meta.json \
  username@136.114.243.136:/tmp/

# 2. Создать директорию в контейнере и скопировать
docker exec gestalt-supervisor-app-1 mkdir -p /app/data/docs/smart
docker cp /tmp/book.txt gestalt-supervisor-app-1:/app/data/docs/smart/
docker cp /tmp/book.meta.json gestalt-supervisor-app-1:/app/data/docs/smart/

# 3. Запустить ingest
curl -X 'POST' \
  'http://136.114.243.136:8000/api/admin/files/ingest?filename=smart:book.txt&source_type=session_guides' \
  -H 'accept: application/json'
```

### Re-ingest (после исправления багов или обновления данных)

`ingest` автоматически удаляет старые чанки файла и записывает новые — просто вызови повторно:

```bash
curl -X 'POST' 'http://136.114.243.136:8000/api/admin/files/ingest?filename=smart:book.txt&source_type=session_guides' -H 'accept: application/json'
```

---

## Полезные команды на VM

```bash
# Статус контейнеров
docker ps

# Логи приложения
docker logs <container_id> -f

# Перезапустить стек (если что-то пошло не так)
docker compose -f /opt/psyai/docker-compose.yml restart

# Удалить все остановленные контейнеры (перед пересозданием стека)
docker rm -f $(docker ps -aq)
```

---

## Проблемы и решения

| Проблема | Причина | Решение |
|---|---|---|
| `service account not found` | Удалён дефолтный SA | Создать `compute-default` в IAM |
| `ZONE_RESOURCE_POOL_EXHAUSTED` | Нет ресурсов в us-central1-a | Переключиться на us-central1-f |
| `port 8000 already allocated` | Portainer занял порт | Пересоздать Portainer на 9000/9443 |
| `reference not found` | Ветка `main` не существует | Использовать `refs/heads/master` |
| `.env.docker not found` | Файл в .gitignore | Убрать `env_file`, переменные через `environment:` с дефолтами |
| Portainer: stack created outside | Контейнеры от старого запуска | `docker rm -f $(docker ps -aq)` |
| `telegram.error.Conflict` | Два экземпляра бота (локальный + сервер) | Остановить локальный: `docker compose down` |
| `embeddings: {}` в `/files/status` | Данные в Qdrant записаны с неверным `source_file` | Сделать re-ingest всех файлов |
