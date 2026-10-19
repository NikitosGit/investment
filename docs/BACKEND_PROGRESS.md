# Backend — журнал реализации

Отметки о выполнении этапов и результаты ревью по skill `code-review-and-quality`.
План: [`BACKEND_PLAN.md`](BACKEND_PLAN.md).

## Этап 0. Каркас, конфигурация, логирование, health — ✅ выполнено

**Реализовано**

- `backend/pyproject.toml` (uv, зависимости, ruff, pytest, coverage), `.env.example`, `.gitignore`, `README.md`.
- `app/core/`: `config.py` (Pydantic Settings, CORS-строки, валидация), `logging.py` (JSON/text формат, request_id), `errors.py` (`AppError`, коды, единый формат), `time.py` (UTC и настраиваемая таймзона).
- `app/db/`: `base.py` (DeclarativeBase + naming convention), `session.py` (engine, SQLite PRAGMA, session factory, `get_db`).
- `app/api/`: `deps.py`, `router.py`, `routes/health.py`.
- `app/main.py`: фабрика приложения, lifespan, CORS, middleware X-Request-ID, обработчики ошибок.
- `tests/`: `conftest.py` (изоляция схемы БД, temp-каталог), `test_health.py`.

**Проверка**

- `uv run ruff check .` — без ошибок.
- `uv run ruff format --check .` — без изменений.
- `uv run pytest` — 3 passed.
- Ручная проверка: `GET /api/health` → `{"status":"ok",...,"moex":"unknown"}`, `/openapi.json` содержит `/api/health`.

**Ревью (независимый агент, 5 осей)**

- Required 1: `tzdata` не был объявлен прямой зависимостью (Windows `ZoneInfo`) — добавлен в `pyproject.toml`.
- Required 2: `X-Request-ID` терялся на необработанных 500 — id кладется в `request.state` и возвращается из обработчика.
- Required 3: `TIMEZONE` был no-op — хелперы времени читают настройку; `MOSCOW_TZ` заменен на `local_timezone()`.
- Optional: изоляция БД между тестами (autouse fixture со `drop_all/create_all`), удален `pool_pre_ping` для SQLite, русские сообщения для общих HTTP-ошибок, ограничение длины входящего `X-Request-ID`, удален неиспользуемый код схем.
- Осталось на будущее (не блокер): `moex` в health станет реальным на этапе 2; перенос части настроек в `SettingsService` на этапе 8.

## Этапы 1–9

Статусы отмечаются по мере выполнения.
