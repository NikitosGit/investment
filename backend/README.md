# Учет инвестиций — backend

Локальный REST API для учета одного инвестиционного портфеля: акции и облигации
РФ, операции покупки/продажи, средневзвешенная цена, котировки MOEX ISS, купоны,
амортизация, дивиденды, дашборд, резервные копии и экспорт.

- Python 3.12, FastAPI, SQLAlchemy 2 (sync), SQLite (WAL), Alembic, Pydantic v2.
- MOEX ISS через `httpx`, повторы `tenacity`, планировщик `APScheduler`.
- Деньги хранятся в копейках, цены — в миллионных долях рубля, без `float`.
- Swagger UI: `/docs`, OpenAPI JSON: `/openapi.json`.
- Спецификация: [`../docs/BACKEND_PLAN.md`](../docs/BACKEND_PLAN.md).

## Требования

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Установка и запуск

```bash
cd backend
uv sync
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
uv run alembic upgrade head   # создать/обновить схему БД
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Проверка и документация:

```bash
curl http://127.0.0.1:8000/api/health
# Swagger UI: http://127.0.0.1:8000/docs
# OpenAPI:    http://127.0.0.1:8000/openapi.json
```

При первом обращении приложение создает единственный портфель «Мой портфель».
Каталоги `data/` и `data/backups/` создаются автоматически.

## Конфигурация

Настройки читаются из переменных окружения и файла `.env` в каталоге запуска.
Шаблон — [`.env.example`](.env.example).

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `APP_ENV` | Окружение: `local`, `test`, `prod` | `local` |
| `APP_VERSION` | Версия приложения в API и health | `0.1.0` |
| `DATABASE_URL` | URL SQLite-базы | `sqlite:///./data/investments.db` |
| `DATA_DIR` | Каталог данных | `./data` |
| `BACKUP_DIR` | Каталог резервных копий | `./data/backups` |
| `MOEX_BASE_URL` | Базовый URL MOEX ISS | `https://iss.moex.com/iss` |
| `MOEX_TIMEOUT_SECONDS` | Таймаут запроса к MOEX, сек | `10` |
| `MOEX_RETRIES` | Число повторов при сбое MOEX | `3` |
| `MOEX_USER_AGENT` | User-Agent для MOEX | `investment-tracker/0.1` |
| `QUOTE_REFRESH_ENABLED` | Master switch автоматического обновления котировок | `true` |
| `QUOTE_REFRESH_HOUR` | Час ежедневного обновления (локальная таймзона) | `19` |
| `QUOTE_REFRESH_MINUTE` | Минута ежедневного обновления | `5` |
| `TIMEZONE` | Таймзона дат и расписания | `Europe/Moscow` |
| `CORS_ORIGINS` | Разрешенные origin через запятую | `http://localhost:4200,http://127.0.0.1:4200` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |

### Автоматическое обновление котировок

`QUOTE_REFRESH_ENABLED` — настройка развертывания с приоритетом:

- `false` — планировщик не создается, автоматические обновления выключены;
  `PATCH /api/settings` с `quote_refresh_enabled=true` вернет `400`.
- `true` — планировщик работает, а сохраненная в БД настройка
  `quote_refresh_enabled` (по умолчанию `true`) включает или выключает плановые
  запуски.

Ручной `POST /api/quotes/refresh` не зависит от этих флагов. Последний refresh
виден в `GET /api/health` (`moex`: `ok`/`error`/`unknown`).

## Демо-данные

```bash
uv run python -m app.scripts.seed_demo
```

Seed не обращается к сети и создает:

- портфель «Мой портфель»;
- SBER: 2 покупки и 1 продажа (15 шт., средняя 110.00);
- ОФЗ 26238: покупка 15 шт. по 95.123%, амортизация 200.00 на единицу;
- 54 ручные котировки: 27 дат × 2 инструмента (еженедельно за полгода и на сегодня);
- фактический дивиденд 200.00, фактический купон 525.00 и 3 ожидаемых купона;
- snapshot портфеля на текущую дату.

Повторный запуск идемпотентен: версия и дата-якорь хранятся в `app_setting`
(`demo_seed_version`, `demo_seed_anchor`), поэтому данные не дублируются и не
сдвигаются по датам. Прерванный запуск можно безопасно повторить.

## Endpoint-ы

- Служебные: `GET /api/health`, `GET /docs`, `GET /openapi.json`.
- Портфель: `GET/PATCH /api/portfolio`.
- Активы: `GET/POST /api/assets`, `GET /api/assets/search?q=`,
  `GET /api/assets/{asset_id}`, `POST /api/assets/{asset_id}/refresh`,
  `DELETE /api/assets/{asset_id}`.
- Операции: `GET/POST /api/operations`, `PATCH/DELETE /api/operations/{operation_id}`.
- Позиции: `GET /api/positions`.
- Доходы: `GET/POST /api/income`, `PATCH/DELETE /api/income/{income_id}`,
  `POST /api/income/{income_id}/mark-paid`.
- Котировки: `GET /api/quotes/{asset_id}/history?period=`,
  `POST /api/quotes/refresh`, `POST /api/quotes/manual`.
- Дашборд и история: `GET /api/dashboard?period=1M|3M|1Y|ALL`,
  `GET /api/snapshots?period=`.
- Настройки: `GET/PATCH /api/settings`.
- Backup и экспорт: `POST /api/backup`, `GET /api/export?format=json|csv`.

Формат ошибок единый: `{"error": {"code", "message", "details"}}`, деньги и
цены в ответах — строки (`"1234.56"`, `"110.000000"`).

## Backup и экспорт

```bash
uv run python -m app.scripts.backup
```

или `POST /api/backup`. Резервная копия создается через SQLite backup API
(WAL-safe), поэтому файл `.db` в `data/backups/` — канонический и пригодный для
восстановления. Источник открывается read-only и проверяется на наличие схемы.
Backup-файлы не отдаются по HTTP; API возвращает только путь.

`GET /api/export?format=json` — человекочитаемая API-проекция (портфель, активы,
операции, доходы, котировки, амортизация, snapshots, настройки). Это не
lossless-формат восстановления. `format=csv` возвращает ZIP с `positions.csv`,
`operations.csv` и `income.csv` (UTF-8 BOM, CRLF, защита от формул).

## Тесты, линтер, покрытие

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
```

Тесты не используют сеть: ответы MOEX подменяются `respx` и фикстурами.
Текущее состояние: **461 passed**, покрытие **98%** (сервисы — 98.6%,
провайдеры — 95.1%). Если `uv` не в `PATH`, используйте `python -m uv run ...`
для любой команды.

## Передача frontend

- Base URL: `http://127.0.0.1:8000/api`.
- Swagger UI: `http://127.0.0.1:8000/docs`.
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`.
- CORS: `http://localhost:4200` (и `127.0.0.1:4200`) по умолчанию.
- Авторизации нет; сервис рассчитан на локальный запуск (`127.0.0.1`).
- Все деньги/цены — строки; даты — `YYYY-MM-DD`; ошибки — `error.code`.
- Демо-данные позволяют разрабатывать UI без MOEX.

Пример генерации TypeScript-типов:

```bash
npx openapi-typescript http://127.0.0.1:8000/openapi.json -o src/app/api/schema.ts
```

## Диагностика

- **`uv` не найден в PATH** — запускайте команды через `python -m uv ...`.
- **Таблицы не созданы / health предупреждает о БД** — выполните
  `uv run alembic upgrade head`.
- **MOEX недоступен** — приложение продолжает работать на кэше котировок;
  `GET /api/health` покажет `moex=error` или `unknown`, плановый/ручной refresh
  можно повторить позже. Демо-данные работают полностью офлайн.
- **Сбросить демо-базу** — остановите сервер, при необходимости сохраните копию,
  удалите `data/investments.db` (и `-wal`/`-shm`, если есть), затем выполните
  `uv run alembic upgrade head` и `uv run python -m app.scripts.seed_demo`.
  В PowerShell: `Remove-Item data/investments.db*`.

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
| 9. Тесты, OpenAPI, README, seed demo | ✅ готово |
