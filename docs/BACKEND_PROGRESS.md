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

## Этап 1. Модели, Alembic, миграции, seed портфеля — ✅ выполнено

**Реализовано**

- `app/db/enums.py`: `AssetType`, `OperationType`, `PriceType`, `IncomeKind`, `IncomeStatus`, `DataSource` (StrEnum).
- `app/db/base.py`: `db_enum()` — enum как `VARCHAR` без native enum (SQLite).
- `app/db/models/`: `portfolio`, `asset`, `operation`, `income`, `quote`, `bond_amortization`, `portfolio_snapshot`, `app_setting` — поля, nullable, уникальные ограничения, индексы и CHECK-и по разделу 5 плана.
- Деньги/цены — только `INTEGER` (копейки / микро-рубли), `float` отсутствует.
- Alembic: `alembic.ini`, `app/db/migrations/env.py` (URL из настроек, `render_as_batch`), начальная миграция `690d3381668c`.
- `portfolio_service` и `GET/PATCH /api/portfolio`; единственный портфель создается в lifespan.
- Ограничение единственного портфеля на уровне БД: `CHECK (id = 1)`.
- `UtcDatetime`: naive-UTC значения отдаются как ISO 8601 с таймзоной.
- Тесты: `test_models.py` (enum round-trip, уникальность, CHECK-и, NULL в unique), `test_migrations.py` (upgrade/downgrade на чистой БД), `test_portfolio.py`.

**Проверка**

- `uv run ruff check .` — чисто; `uv run ruff format --check .` — чисто.
- `uv run pytest` — 18 passed.
- `alembic upgrade head` / `downgrade base` / `upgrade head` — без ошибок; `alembic check` — «No new upgrade operations detected» (модели и миграция синхронны).
- Ручная проверка: `GET /api/portfolio` создает и возвращает портфель, `PATCH` переименовывает и сохраняет.

**Ревью (независимый агент, 5 осей)**

- Critical/Required — нет.
- Optional 1: GET с побочным эффектом создания — оставлен как ленивая инициализация, дублирование устранено ограничением `CHECK (id = 1)`.
- Optional 2: добавлено ограничение единственной строки портфеля + тест.
- Optional 3: добавлены тесты CHECK для цены операции, котировки, амортизации и уникальности `external_id` с несколькими NULL.
- Nit: восходящие индексы вместо DESC (SQLite сканирует в обе стороны), `String(3)` вместо `CHAR(3)`, плоская раскладка тестов — принято, раскладка `unit/integration` будет на этапе 9.

## Этап 2. MOEX client — ✅ выполнено

**Реализовано**

- `app/core/enums.py`: доменные enum-ы перенесены из `app/db` (провайдер не зависит от слоя БД).
- `app/core/money.py`: `Decimal`-хелперы `rubles_to_micro/kopecks`, обратные конверсии и форматирование по контракту API; `float` не используется.
- `app/providers/moex/`:
  - `client.py` — `MoexClient` (sync `httpx`): `search_securities`, `get_security_info`, `get_current_quote`, `get_history` (пагинация), `get_bondization`; retry (N попыток = retries + 1, экспоненциально 0.5/1/2 с), троттлинг ≤3 rps, `User-Agent`, `from_settings`.
  - `mapper.py` — толерантный парсинг таблиц ISS: фильтр `is_traded`/`TQBR`/`TQCB`, приоритет `LAST→LCURRENTPRICE→MARKETPRICE→PREVPRICE`, `CLOSE`→`LEGALCLOSEPRICE`, `value_rub`→`value`, учёт регистра полей.
  - `errors.py` — `MOEX_UNAVAILABLE`(502), `MOEX_NOT_FOUND`(404), `MOEX_PARSE_ERROR`(502).
  - `schemas.py` — dataclass-результаты, независимые от БД и API.
- `app/api/error_handlers.py`: FastAPI-обработчики вынесены из `app/core/errors.py`, который стал framework-free (провайдер больше не тянет FastAPI).
- Тесты: `test_money.py`, `test_moex_mapper.py`, `test_moex_client.py` (respx, JSON-фикстуры `tests/fixtures/moex/`), без сетевых вызовов.

**Проверка**

- `uv run ruff check .` / `ruff format --check .` — чисто.
- `uv run pytest` — 72 passed; покрытие `app/providers` 95% (client 98%, mapper 92%), общее 93%.
- Сетевые вызовы отсутствуют: всё через `respx`.

**Ревью (независимый агент, 5 осей)**

- Required 1: `retries=3` давал 3 попытки (2 задержки) вместо 3 retry — исправлено на `retries + 1` попыток, есть тест на число вызовов.
- Required 2: некорректные `FACEVALUE`/`LOTSIZE` давали 500 — добавлены guard-ы с `MOEX_PARSE_ERROR` и тесты.
- Required 3 (архитектура): провайдер транзитивно импортировал FastAPI — `AppError`/`ErrorCode` вынесены в framework-free `app/core/errors.py`, обработчики — в `app/api/error_handlers.py`.
- Optional: `429` теперь retryable; при запросе несуществующего борда `get_security_info` возвращает not found, а не первую попавшуюся строку.
- Добавлены тесты: приоритет цены (все 4 поля), котировка облигации в процентах, `User-Agent`/`from_settings`, троттлинг, ограничение пагинации, невалидный JSON/не-объект/4xx.
