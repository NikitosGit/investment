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

Если `uv` не в PATH, те же команды запускаются через `python -m uv ...`.

## Реализованные endpoint-ы

- Служебные: `GET /api/health`.
- Портфель: `GET/PATCH /api/portfolio`.
- Активы: `GET/POST /api/assets`, `GET /api/assets/search`, `GET /api/assets/{id}`, `POST /api/assets/{id}/refresh`, `DELETE /api/assets/{id}`.
- Операции и позиции: `GET/POST/PATCH/DELETE /api/operations`, `GET /api/positions`.
- Доходы: `GET/POST/PATCH/DELETE /api/income`, `POST /api/income/{id}/mark-paid`.
- Котировки: `GET /api/quotes/{asset_id}/history`, `POST /api/quotes/refresh`, `POST /api/quotes/manual`.
- Дашборд и история: `GET /api/dashboard?period=1Y`, `GET /api/snapshots?period=1Y`.
- Настройки: `GET/PATCH /api/settings`.
- Backup и экспорт: `POST /api/backup`, `GET /api/export?format=json|csv`.

Резервная копия создается командой `python -m app.scripts.backup`
(через `python -m uv run python -m app.scripts.backup`, если `uv` не в PATH) или
`POST /api/backup` и представляет собой консистентную копию SQLite.
JSON-экспорт предназначен для просмотра; каноническая резервная копия — файл `.db`.

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
| 3. Активы | ✅ готово |
| 4. Операции и позиции | ✅ готово |
| 5. Доходы | ✅ готово |
| 6. Котировки и планировщик | ✅ готово |
| 7. Дашборд и snapshots | ✅ готово |
| 8. Настройки, backup, export | ✅ готово |
| 9. Тесты, OpenAPI, README, seed | ⏳ |
