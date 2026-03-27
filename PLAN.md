# Супервизор в кармане — План реализации

## Этапы

### Этап 1. Инфраструктура ✅
- [x] `docker-compose.yml` — 4 сервиса: app, redis, qdrant, postgres
- [x] `.env.example` — все переменные окружения
- [x] `Dockerfile` с uv (Python 3.11)
- [x] Персистентные данные через Docker volumes (app_data, redis_data, qdrant_data)

### Этап 2. Подготовка данных ✅
- [x] `ingest/standard.py` — pymupdf4llm → очистка → `data/docs/standard/`
- [x] `ingest/smart.py` — Gemini Vision → Semantic Markdown → `data/docs/smart/`
- [x] Данные: `smart/joyce_sills.txt`, `smart/mann_100_key_points.txt`

### Этап 3. База данных ⏳ (отложено)
- [ ] `app/db/models.py` — SQLAlchemy модели (users, subscriptions)
- [ ] `app/db/database.py` — подключение к PostgreSQL
- [ ] Alembic миграции

### Этап 4. Векторное хранилище ✅
- [x] `app/vector_store.py` — Qdrant + чанкинг + эмбеддинги Gemini
- [x] `app/services/search.py` — семантический поиск
- [x] Динамические коллекции: `{source_type}_{mode}`

### Этап 5. Кэш ✅
- [x] `app/services/cache.py` — Redis кэш ответов (TTL 30д)
- [x] Структура для истории (get_history/push_history) — готова, но не подключена к RAG

### Этап 6. RAG пайплайн ✅
- [x] `app/services/rag.py` — поиск в Qdrant + генерация через Gemini
- [x] Кэш ответов (Redis)
- [x] Каналы: `api` и `telegram` (разные промпты)

### Этап 7. Admin API ✅
- [x] Swagger UI: `/swagger`
- [x] `POST /api/admin/files/upload` — загрузка PDF
- [x] `GET /api/admin/files/status` — статус файлов с инфо из Qdrant
- [x] `POST /api/admin/files/convert` — PDF → Semantic Markdown
- [x] `GET /api/admin/files/docs` — список готовых текстов
- [x] `POST /api/admin/files/ingest` — текст → Qdrant
- [x] `DELETE /api/admin/files/ingest` — удалить чанки файла
- [x] `GET /api/admin/search` — семантический поиск (дебаг)
- [x] `DELETE /api/admin/cache` — сброс Redis кэша
- [x] `GET /api/admin/collections` — статус коллекций Qdrant
- [x] `POST /api/admin/ragas` — запуск RAGAS оценки (фоново)
- [x] `GET /api/admin/ragas/results` — результаты оценки

### Этап 8. Telegram бот ✅
- [x] `app/bot/handlers.py` — polling и webhook режимы
- [x] `/start` — приветственное сообщение с примерами
- [x] `/help` — описание системы и базы знаний
- [x] Обработка сообщений → RAG → HTML-ответ
- [x] Разбивка длинных ответов (лимит 4096 символов)

---

## Следующие этапы (TODO)

- [ ] **История диалога** — подключить `get_history/push_history` к RAG пайплайну
- [ ] **Персонализация** — адаптировать ответ под контекст конкретного пользователя
- [ ] **База данных пользователей** — регистрация, подписки (Этап 3)
- [ ] **Голосовые сообщения** — Gemini Audio API
- [ ] **Перевод базы знаний** — русскоязычные чанки для лучшего поиска
