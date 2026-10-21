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

## Этап 3. AssetService + API активов — ✅ выполнено

**Реализовано**

- `app/services/asset_service.py`: `list_assets`, `get_asset` (404 `ASSET_NOT_FOUND`), `search_moex`, `create_from_moex`, `refresh_asset`, `delete_asset`; нормализация тикера, проверка дубля до запроса в MOEX, атомарное создание/обновление (rollback при ошибке MOEX), `AssetCard` + `get_asset_card`.
- `app/services/bondization_service.py`: идемпотентный upsert купонов (`EXPECTED`, только будущие, PAID не перезаписываются) и амортизации по `external_id`; `current_face_value_kopecks` (номинал минус амортизация, не ниже 0), `list_amortizations`.
- `app/services/portfolio_service.py`: `ensure_default_portfolio(commit=False)` — создание портфеля в общей транзакции без скрытого commit.
- `app/schemas/asset.py`: ответы с деньгами-строками (`initial_face_value`, `current_face_value`, `amount_per_unit`), `AssetDetail.from_asset`.
- `app/api/routes/assets.py`: `GET /api/assets`, `GET /api/assets/search`, `POST /api/assets` (201), `GET /api/assets/{id}`, `POST /api/assets/{id}/refresh`, `DELETE /api/assets/{id}` (204).
- `app/api/deps.py` + `app/main.py`: единый `MoexClient` в `app.state`, `MoexDep`, закрытие клиента на shutdown.
- Тесты: 21 API/service-тест на respx (поиск, создание акции/облигации, атомарность, дубликат в другом регистре, type mismatch, отсутствие номинала, refresh, delete rules, OpenAPI).

**Проверка**

- `uv run ruff check .` / `ruff format --check .` — чисто.
- `uv run pytest` — 102 passed; покрытие `app/services` — 100% (188 stmts, 38 branches).
- Сеть не используется, все MOEX-ответы — фикстуры `tests/fixtures/moex/`.

**Ревью (независимый агент, 5 осей + повторная проверка исправлений)**

- Required 1: создание облигации коммитило актив до загрузки bondization → при ошибке MOEX оставался «битый» актив. Исправлено: `flush` → синхронизация → один `commit`, rollback при ошибке; тест 502 + пустой список активов.
- Required 2: свежедобавленную облигацию нельзя было удалить из-за EXPECTED-купонов. Исправлено: блокируют только операции и PAID-доходы; EXPECTED-купоны удаляются вместе с активом.
- Optional: сборка карточки перенесена в сервис; `secid` нормализуется (регистронезависимый дубль, индекс); убран скрытый commit в синхронизации; добавлен OpenAPI smoke-тест и тесты type mismatch/отсутствующего номинала.
- Повторное ревью: PASS по всем 6 пунктам, новых Critical/Required нет.
- Отложено осознанно: загрузка текущей цены и истории при добавлении актива (§7.7 шаг 4) — этап 6 (`QuoteService`); N+1 upsert и очистка устаревших EXPECTED при синхронизации — не критичны для MVP.

## Этап 4. OperationService + PositionService + API — ✅ выполнено

**Реализовано**

- `app/core/money.py`: точные Decimal-хелперы `percent_price_to_micro`, `price_micro_to_percent_micro`, `quantity_cost_kopecks`, `bond_market_value_kopecks`, `format_ratio` (ROUND_HALF_UP, без float).
- `app/services/operation_service.py`: CRUD операций, нормализация цены (акции — только RUB; облигации — RUB/PERCENT, номинал фиксируется на дату сделки), повторный replay всей истории при create/update/delete с rollback; смена только `price_type` сохраняет `price_micro` без изменений; PATCH даты/типа пересчитывает цену; 409 `INSUFFICIENT_QUANTITY` для запрещённых продаж.
- `app/services/position_service.py`: `PositionState`/`PositionView`, replay по `(trade_date, id)`, пропорциональное списание себестоимости, средняя цена, оценка по последней котировке (`PERCENT` для облигаций MOEX и `RUB` для ручных), cost-fallback (`price_source="COST"`, `is_stale=true`), доли от итоговой стоимости портфеля.
- `app/services/quote_service.py`: read-only `get_last_quote` (последняя котировка `<= on_date`); refresh/backfill/ручные котировки — этап 6.
- `app/schemas/operation.py`, `app/schemas/position.py`: контракты §8.4/§8.5, деньги и цены строками (2 и 6 знаков).
- `app/api/routes/operations.py`: `GET/POST/PATCH/DELETE /api/operations`; `app/api/routes/positions.py`: `GET /api/positions`.
- Тесты: replay-математика, продажа больше остатка, обратные даты, облигации (%, RUB, амортизация), cost-fallback, доли, API-контракты, OpenAPI.

**Проверка**

- `uv run ruff check .` / `ruff format --check .` — чисто.
- `uv run pytest` — 155 passed.
- Покрытие: `app/services` — 97%, `app/core/money.py` — 100%, суммарно 98%.

**Ревью (независимый агент, 5 осей + повторная проверка исправлений)**

- Critical/Required дефектов кода нет.
- Required (тесты): добавлены регрессии на PATCH даты SELL до BUY и смены BUY→SELL без остатка (409 + неизменная история); тест оценки облигации с амортизацией (котировка до амортизации оценивается по номиналу на дату котировки, после — по новому номиналу).
- Optional исправлено: оценка облигации учитывает `quote.price_type`; `share` в `get_position` считается от итогов портфеля, а не всегда 1; смена только `price_type` сохраняет нормализованную цену; понятная ошибка для PERCENT у акций; guard-тесты на округление процента в 0 и полностью амортизированный номинал.
- Nit исправлен: `_switch_price_type` не пропускает процент, округлившийся в 0.
- Повторное ревью: PASS по всем пунктам, новых блокеров нет.
- Отложено: N+1 при оценке позиций (приемлемо для локального MVP); `is_stale` для котировок предыдущих дней — уточнить с фронтендом; `avg_price_percent` после амортизации считается от текущего номинала (display-only).
