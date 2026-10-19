# Учет инвестиций — backend

Локальный REST API для учета инвестиционного портфеля: акции и облигации РФ,
операции покупки/продажи, средневзвешенная цена, котировки и купоны MOEX ISS,
доходы, дашборд, экспорт и резервные копии.

- Python 3.12, FastAPI, SQLAlchemy 2, SQLite, Alembic, Pydantic v2
- Документация API: Swagger UI `/docs`, OpenAPI JSON `/openapi.json`
- Спецификация: [`../docs/BACKEND_PLAN.md`](../docs/BACKEND_PLAN.md)

## Требования

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Установка и запуск

```bash
cd backend
uv sync
cp .env.example .env
uv run alembic upgrade head   # применить миграции
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Проверка:

```bash
curl http://127.0.0.1:8000/api/health
```

Swagger UI: <http://127.0.0.1:8000/docs>

## Конфигурация

Все настройки читаются из переменных окружения и файла `.env`.
Шаблон — [`.env.example`](.env.example). Ключевые параметры:

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `DATABASE_URL` | SQLite URL | `sqlite:///./data/investments.db` |
| `DATA_DIR` | Каталог данных | `./data` |
| `BACKUP_DIR` | Каталог резервных копий | `./data/backups` |
| `MOEX_BASE_URL` | Базовый URL MOEX ISS | `https://iss.moex.com/iss` |
| `CORS_ORIGINS` | Разрешенные origin через запятую | `http://localhost:4200,...` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |

## Тесты и линтер

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
```

## Миграции

```bash
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "describe change"
```

Проверка на чистой базе:

```bash
rm -f data/investments.db
uv run alembic upgrade head
```

## Статус реализации

| Этап | Статус |
|---|---|
| 0. Каркас, конфигурация, логирование, health | ✅ готово |
| 1. Модели, миграции | ✅ готово |
| 2. MOEX client | ✅ готово |
| 3. Активы | ⏳ |
| 4. Операции и позиции | ⏳ |
| 5. Доходы | ⏳ |
| 6. Котировки и планировщик | ⏳ |
| 7. Дашборд и snapshots | ⏳ |
| 8. Настройки, backup, export | ⏳ |
| 9. Тесты, OpenAPI, README, seed | ⏳ |
