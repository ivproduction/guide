# Супервизор в кармане — Архитектура

## Назначение

Telegram-бот для начинающих гештальт-терапевтов.
Терапевт задаёт вопрос о ведении сессии — бот отвечает на основе профессиональной литературы.

**База знаний:**
- Phil Joyce & Charlotte Sills — *Skills in Gestalt Counselling & Psychotherapy* (3rd ed.)
- Dave Mann — *Gestalt Therapy: 100 Key Points and Techniques* (2nd ed.)

---

## Стек (Docker Compose)

```
┌─────────────────────────────────────────┐
│           Telegram Bot                  │
│       (python-telegram-bot)             │
│   polling (локально) / webhook (VPS)    │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│           app (Python / FastAPI)        │
│                                         │
│  1. Redis: проверить кэш(вопрос)        │
│  2. Qdrant: embed(вопрос) → top-5 чанков│
│  3. Gemini: [чанки] + вопрос → ответ   │
│  4. Redis: сохранить ответ в кэш        │
│  5. Telegram: отправить ответ           │
└──────────┬──────────────────────────────┘
           │                    │
           ▼                    ▼
    ┌────────────┐       ┌────────────┐
    │   Redis    │       │   Qdrant   │
    │            │       │            │
    │ cache:     │       │ векторы    │
    │  TTL 30д   │       │ книг       │
    └────────────┘       └────────────┘
```

---

## RAG пайплайн (текущая реализация)

```
вопрос
  → Redis: cache:{SHA256(вопрос)} → HIT → вернуть кэш
  → MISS → Gemini Embeddings → вектор запроса
         → Qdrant: top-5 чанков по косинусной близости
         → Gemini: [system_prompt] + [чанки] + вопрос → ответ
         → Redis: сохранить ответ (TTL: 30 дней)
         → вернуть ответ
```

**Каналы генерации:** `api` (обычный текст) и `telegram` (HTML-форматирование с эмодзи).
Каждый канал использует свои system_prompt и RAG_prompt.

---

## Пайплайн добавления книги

```
PDF (data/raw/)
  → POST /api/admin/files/convert
      Gemini Vision: PDF → Semantic Markdown
      MarkdownHeaderTextSplitter: разбивка по заголовкам
      → data/docs/smart/{name}.txt

  → POST /api/admin/files/ingest
      текст → чанки по 800 симв. (overlap 100)
      Gemini Embeddings: чанк → вектор 768d
      → Qdrant: коллекция session_guides_smart
```

**Коллекция:** `{source_type}_{mode}` — например `session_guides_smart`

---

## Структура файлов

```
guide/
├── docker-compose.yml
├── Dockerfile
├── .env / .env.docker / .env.example
├── pyproject.toml
│
├── app/
│   ├── main.py             ← FastAPI + lifespan (бот startup/shutdown) + webhook route
│   ├── config.py           ← настройки из .env
│   │
│   ├── api/
│   │   ├── admin.py        ← /api/admin/* — управление данными и оценка
│   │   └── chat.py         ← /api/app/* — RAG чат (API)
│   │
│   ├── bot/
│   │   └── handlers.py     ← Telegram: /start, /help, обработка сообщений
│   │
│   ├── services/
│   │   ├── rag.py          ← RAG пайплайн (поиск + генерация)
│   │   ├── search.py       ← семантический поиск по Qdrant
│   │   └── cache.py        ← Redis кэш + структура для истории (TODO)
│   │
│   ├── ingest/
│   │   ├── __init__.py     ← convert_file() — роутер standard/smart
│   │   ├── standard.py     ← pymupdf4llm → текст
│   │   ├── smart.py        ← Gemini Vision → Semantic Markdown
│   │   └── _common.py      ← skip_intro()
│   │
│   ├── ragas/
│   │   ├── eval.py         ← RAGAS оценка качества
│   │   └── questions.py    ← тест-вопросы
│   │
│   ├── vector_store.py     ← чанкинг + эмбеддинг + загрузка в Qdrant
│   └── db/                 ← PostgreSQL (пока не используется)
│
└── data/                   ← Docker volume (персистентно)
    ├── raw/                ← исходные PDF
    ├── docs/
    │   ├── standard/       ← конвертированные тексты (standard mode)
    │   └── smart/          ← конвертированные тексты (smart mode)
    └── ragas/              ← отчёты RAGAS
```

---

## Redis — схема ключей

```
cache:{SHA256(вопрос)}   → ответ (строка)    TTL: 30 дней
history:{user_id}        → Redis List        TTL: 14 дней  ← структура готова, не подключена
```

---

## Admin API — эндпоинты

Swagger: `http://localhost:8000/swagger`

| Метод | Endpoint | Действие |
|---|---|---|
| `POST` | `/api/admin/files/upload` | Загрузить PDF |
| `GET` | `/api/admin/files/status` | Статус файлов (конвертация + Qdrant) |
| `POST` | `/api/admin/files/convert` | PDF → Semantic Markdown |
| `GET` | `/api/admin/files/docs` | Список готовых текстов |
| `POST` | `/api/admin/files/ingest` | Текст → Qdrant |
| `DELETE` | `/api/admin/files/ingest` | Удалить чанки файла |
| `GET` | `/api/admin/search` | Семантический поиск (дебаг) |
| `DELETE` | `/api/admin/cache` | Сброс Redis кэша |
| `GET` | `/api/admin/collections` | Статус коллекций Qdrant |
| `POST` | `/api/admin/ragas` | Запустить RAGAS оценку (фоново) |
| `GET` | `/api/admin/ragas/results` | Результаты RAGAS |

---

## TODO (следующие этапы)

- **История диалога** — подключить `get_history/push_history` к RAG: персонализация ответа под контекст конкретного терапевта
- **База пользователей** — PostgreSQL: регистрация, подписки
- **Голосовые сообщения** — Gemini Audio API
- **Перевод базы знаний** — улучшит точность кросс-языкового поиска
