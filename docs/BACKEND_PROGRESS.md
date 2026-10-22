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

## Этап 5. IncomeService: купоны, амортизация, mark-paid, дивиденды — ✅ выполнено

**Реализовано**

- `app/services/income_service.py` (+ `income_rules.py`): `list`, `build_views`/`list_income_views`, `create_manual`, `update_income`, `mark_paid`, `delete_income`, `expected_amount`, `current_quantity`, `totals`, `sync_coupons`.
- `app/schemas/income.py`: контракт §8.6 — деньги строками с 2 знаками (`"10.00"`), `is_overdue`, `totals` (`dividends_paid`, `coupons_paid`, `expected_coupons`), `extra="forbid"`, очистка `record_date`/`note`.
- `app/api/routes/income.py`: `GET /api/income` (фильтры `status`, `kind`, `asset_id`, `from`, `to`; итоги по портфелю), `POST` (201), `PATCH`, `POST /{id}/mark-paid`, `DELETE` (204).
- `app/core/money.py`: `micro_to_kopecks` (1 копейка = 10 000 микро), `unit_price_from_total_micro`.
- Правила: ручные доходы всегда `PAID`/`MANUAL`; `quantity` по умолчанию — текущее количество из replay; для `PAID` сумма (`amount_total`) авторитетна, цена за единицу выводится из неё; `EXPECTED` создаются только синхронизацией MOEX на будущие даты (`pay_date >= today`), `PAID` не перезаписываются; повторный `mark-paid` → 409 `INCOME_ALREADY_PAID`; `sync_coupons` не коммитит (транзакцией владеет вызывающий).
- Тесты: сервис (ожидаемые суммы, дефолт количества, инварианты PAID, комбинации полей, mark-paid, totals, overdue), API (фильтры, форматы, коды, валидация, OpenAPI), sync через respx (идемпотентность, граница `pay_date == today`, откат транзакции вызывающим).

**Проверка**

- `uv run ruff check .` / `ruff format --check .` — чисто.
- `uv run pytest` — 243 passed.
- Покрытие: `app/services` — 98% (`income_rules` 99%, `income_service` 95%), `app/core/money.py` — 100%.

**Ревью (независимый агент, 5 осей + повторная проверка исправлений)**

- Critical: нет.
- Required 1: `amount_total` у `PAID` мог незаметно переписываться (явный total + per-unit расходились, а PATCH количества пересчитывал сумму). Исправлено: сумма авторитетна, per-unit всегда выводится из неё; PATCH количества сохраняет записанную сумму; обновлены и добавлены тесты на все комбинации полей.
- Required 2: не было регрессий на просроченные купоны в итогах, на итоги при фильтре и на границу `pay_date == today`. Добавлены; мутанты на `pay_date >= today` и на итоги из отфильтрованного списка падают.
- Optional исправлено: убран скрытый commit в `sync_coupons`; правка per-unit у MOEX `EXPECTED` отклоняется (400); `ge=0` для количества; `extra="forbid"`; очистка `record_date`/`note`; единая константа микро-в-копейку; переименован параметр `status`.
- Nit исправлены: docstring `create_manual`, неиспользуемый параметр в тест-хелпере.
- Повторное ревью: PASS по всем пунктам; новых блокеров нет.
- Отложено: непокрытые rollback-ветки и кэш-ветка `build_views` (защитный код); N+1/двойной replay при списке доходов; `POST /{id}/mark-paid` требует тело; вопрос включения просроченных купонов в `totals.expected_coupons` (сейчас включаются) — уточнить к этапу 7 (дашборд).

## Этап 6. QuoteService: refresh, history, manual, scheduler — ✅ выполнено

**Реализовано**

- `app/services/quote_service.py`: `refresh_asset`, `backfill_history` (с пагинацией клиента, ограничение 10 лет, старт от последней котировки с перекрытием в 1 день или от первой операции), `refresh_all` (lock, изоляция ошибок по активам, запись `last_quote_refresh_at`/статуса), `add_manual`, `get_history`, `sync_asset_quotes`, `_upsert_quote`.
- Кэш котировок: одна строка на `(asset_id, quote_date)`; MOEX никогда не перезаписывает `source=MANUAL`; ручная цена перекрывает любую; `price_type` — RUB для акций, PERCENT для облигаций.
- `app/services/settings_service.py`: key/value `app_setting` (задел под API настроек этапа 8), `last_quote_refresh_at`/`status` (naive UTC).
- `app/schemas/quote.py`, `app/api/routes/quotes.py`: `GET /api/quotes/{asset_id}/history?period=`, `POST /api/quotes/refresh` (409 `REFRESH_IN_PROGRESS` при параллельном запуске), `POST /api/quotes/manual` (201).
- `app/jobs/scheduler.py` + `app/jobs/refresh.py`: `BackgroundScheduler`, cron в таймзоне приложения, отложенный стартовый refresh; job не бросает исключений и владеет своим клиентом/сессией; `lifespan` запускает и останавливает планировщик.
- `GET /api/health`: статус MOEX из последнего refresh (`unknown`/`ok`/`error`).
- Интеграция с активами: создание и refresh актива best-effort подтягивают текущую цену и историю, сбои MOEX не ломают метаданные (§7.7 шаг 4).
- Тесты: upsert/защита MANUAL, backfill (граница, первая операция, перекрытие, CLOSE vs интрадей), refresh_all (счётчики, ошибки, lock, скрытие внутренних деталей), история/period, ручные цены, планировщик, health, настройки.

**Проверка**

- `uv run ruff check .` / `ruff format --check .` — чисто.
- `uv run pytest` — 280 passed.
- Покрытие: `app/services` — 98% (`quote_service` 98%), `app/core/money.py` — 100%; `app/jobs/refresh.py` — 86%.

**Ревью (независимый агент, 5 осей + повторная проверка исправлений)**

- Critical: нет.
- Required 1: `refresh_all` сначала дозагружал историю, а затем интрадей-цену — официальный CLOSE за сегодня затирался и больше не исправлялся (`_default_history_start` = last+1). Исправлено: `refresh_asset` вызывается перед `backfill_history`, старт истории — от последней котировки с перекрытием в 1 день; добавлен регресс, что CLOSE перекрывает интрадей, и что строка вчерашней даты перезапрашивается.
- Required 2: добавлены тесты на ветку «первая операция без котировок» и на защиту/счёт MANUAL при backfill.
- Optional исправлено: `sync_asset_quotes` не пропускает наружу `SQLAlchemyError` после уже закоммиченного актива; `last_refresh_at` в `/refresh` в локальной таймзоне, как в `/health`; внутренние тексты исключений не утекают в `errors[]`; `updated` задокументировано как число обработанных активов; тест планировщика не запускает реальный job; убран недостижимый код; `QUOTE_REFRESH_ENABLED` в тестах задаётся напрямую.
- Повторное ревью: PASS по всем пунктам; новых Critical/Required нет.
- Отложено: непокрыта ветка `refresh_asset` «нет цены» и fallback «нет котировок и операций»; snapshot в ежедневном job — этап 7.

## Этап 7. DashboardService + snapshots — ✅ выполнено

**Реализовано**

- `app/services/dashboard_service.py`: `get_dashboard`, `compute_series`, `value_on_date`, `DASHBOARD_PERIOD_DAYS` (`1M`/`3M`/`1Y`/`ALL`); таймлайн операций/активов/котировок/амортизаций загружается bulk-запросами, ряд строится по дням с последней известной котировкой, облигация в `PERCENT` оценивается по номиналу на дату котировки, при отсутствии цены — cost-fallback и `is_partial` на точку.
- Итоги: `market_value`/`invested` по открытым позициям, `dividends_paid`/`coupons_paid`, `income_paid_total`, `expected_coupons` (просроченные включены), `positions_count`, `assets_count`.
- Ближайшие купоны: `EXPECTED` с `pay_date >= today` и текущим количеством > 0, сортировка `(pay_date, id)`; просроченные в список не попадают, но входят в итоговый `expected_coupons`.
- Семантика текущего состояния: позиции, карточка актива, количество для ожидаемых купонов и текущие итоги дашборда replay-ят операции с `trade_date <= today`; валидация записи операций по-прежнему replay-ит всю историю, поэтому будущие сделки остаются допустимыми.
- `app/services/snapshot_service.py`: `compute_for_date`, `compute_and_store`, `upsert_snapshot` (атомарный SQLite upsert с сохранением `created_at`, только flush), `get_snapshots` (фильтр периода, верхняя граница — сегодня).
- `app/schemas/dashboard.py`, `app/schemas/snapshot.py`; `GET /api/dashboard?period=1Y`; диагностический `GET /api/snapshots?period=1Y`.
- Ежедневный job после успешного обновления котировок считает и коммитит snapshot на сегодня; сбой snapshot откатывается/логируется и не ломает обновление котировок; при `REFRESH_IN_PROGRESS` запуск пропускается.
- Общий хелпер оценки `position_service.market_value_kopecks`; общий replay `apply_operation`; чистые `bondization_service.face_value_from_amortized` / `face_value_on`.
- Тесты: итоги/ряд/API/snapshot/job, границы future/today, амортизация облигаций, fallback без котировок, пустой портфель, границы периода и snapshot, AST-guard на float-литералы.

**Проверка**

- `python -m uv run ruff check .` / `ruff format --check .` — чисто.
- `python -m uv run pytest` — 345 passed.
- Покрытие: общее 97%; новые dashboard/snapshot-модули и `bondization_service.py` — 100%; `position_service.py` — 97%, `income_service.py` — 96%, `jobs/refresh.py` — 88%.

**Ревью (независимый агент, 5 осей + повторные проверки)**

- Required 1: будущие операции расходились с дашбордом/рядом/snapshot, а будущий SELL мог скрыть сегодняшнюю позицию и купоны. Исправлено replay-ем текущего состояния на `today` при сохранении полной истории для валидации записи; добавлены регрессии future BUY/SELL/future-only.
- Required 2: отсутствовала граница `pay_date == today` — добавлена (купон входит в ближайшие и в ожидаемые; `today - 1` не входит в ближайшие, но входит в ожидаемые).
- Required 3 (тесты): мутации границы «сегодня» выживали (фильтр операций, фильтры амортизации) — добавлены тесты на BUY/SELL сегодня и согласованность котировки/амортизации на ту же дату; ревьюер подтвердил, что мутации теперь падают.
- Optional исправлено: общий хелпер оценки + table-driven тест согласованности; атомарный snapshot upsert; возвращён SQL `SUM` для номинала; реальный id портфеля; граница snapshot в 30 дней; общий `DashboardPeriod`; общий тестовый builder; AST-guard на float; проверка, что snapshot действительно вызывается.
- Отложено: тройной replay/N+1 в дашборде (приемлемо для локального MVP); `is_partial` snapshot не хранится (нет колонки); итоги выплат в дашборде всевременные, а `income_paid` snapshot ограничен `pay_date <= date` (будущие `PAID` могут расходиться); `assets_count` считает все активы; ряд начинается с первой операции, а не с начала периода; плановый snapshot пропускается, если ручной refresh держит lock в момент job.

**Отложено**

- Тройной replay/N+1 в дашборде — приемлемо для локального MVP.
- `is_partial` snapshot не хранится: в таблице нет колонки.
- Итоги выплат в дашборде всевременные, а `income_paid` snapshot ограничен `pay_date <= date`; будущие `PAID` могут расходиться.
- `assets_count` считает все активы, а не только с открытыми позициями.
- Ряд начинается с первой операции, а не с начала периода.
- Плановый snapshot пропускается, если ручной refresh держит lock в момент job.
