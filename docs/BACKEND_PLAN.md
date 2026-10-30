# План реализации backend — «Учет инвестиций»

- **Версия:** 1.0
- **Дата:** 2026-10-19
- **Часть:** 1 из 2 (backend → frontend)
- **Связанный документ:** [`PLAN.md`](../PLAN.md)
- **Стек:** Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite, Alembic, Pydantic v2
- **Ориентир:** 6–9 рабочих дней

## Содержание

1. [Цель и границы](#1-цель-и-границы)
2. [Стек и ключевые решения](#2-стек-и-ключевые-решения)
3. [Структура проекта](#3-структура-проекта)
4. [Конфигурация](#4-конфигурация)
5. [Схема базы данных](#5-схема-базы-данных)
6. [Бизнес-правила и расчеты](#6-бизнес-правила-и-расчеты)
7. [Интеграция с MOEX ISS](#7-интеграция-с-moex-iss)
8. [API-контракт](#8-api-контракт)
9. [Сервисы и модули](#9-сервисы-и-модули)
10. [Фоновые задачи и жизненный цикл](#10-фоновые-задачи-и-жизненный-цикл)
11. [Ошибки, логирование, безопасность](#11-ошибки-логирование-безопасность)
12. [Тестирование](#12-тестирование)
13. [Этапы реализации](#13-этапы-реализации)
14. [Критерии готовности](#14-критерии-готовности)
15. [Передача frontend](#15-передача-frontend)
16. [Риски и ограничения](#16-риски-и-ограничения)
17. [Команды запуска](#17-команды-запуска)

## 1. Цель и границы

Реализовать backend-приложение, которое:

- хранит один инвестиционный портфель;
- ведет акции и облигации РФ;
- принимает операции покупки/продажи;
- считает количество и средневзвешенную цену;
- получает котировки, историю цен, купоны и амортизацию из MOEX ISS;
- ведет ожидаемые и фактические купоны, фактические дивиденды;
- отдает данные для дашборда и графика стоимости;
- поддерживает резервное копирование и экспорт;
- предоставляет стабильный REST API и OpenAPI-документацию для Angular-фронтенда.

### Входит в backend

- REST API `/api/*`.
- SQLite + миграции Alembic.
- Интеграция с MOEX ISS.
- Расчет позиций, средней цены, стоимости, доходов.
- Планировщик обновления котировок.
- Тесты, seed демо-данных, инструкция запуска.
- OpenAPI/Swagger для frontend.

### Не входит

- UI, Angular, PrimeNG.
- Авторизация и многопользовательский режим.
- Несколько портфелей.
- Иностранные активы, крипта, валюта.
- Комиссии, налоги, НДФЛ.
- Ожидаемые дивиденды акций и прогнозы.
- Парсинг сторонних сайтов.
- Импорт брокерских отчетов.
- Реализованная прибыль, FIFO, XIRR, TWR.
- Сплиты, конвертации, mergers.
- Торговые операции и брокерские интеграции.

### Граница готовности для frontend

Backend считается готовым к передаче, когда:

- все endpoints из раздела 8 реализованы и описаны в OpenAPI;
- есть демо-данные для запуска frontend без MOEX;
- CORS настроен для `http://localhost:4200`;
- ответы и ошибки стабильны и покрыты тестами;
- есть примеры запросов и модель данных.

## 2. Стек и ключевые решения

| Компонент | Решение |
|---|---|
| Язык | Python 3.12 |
| Web framework | FastAPI |
| ORM | SQLAlchemy 2.0, sync |
| БД | SQLite (WAL) |
| Миграции | Alembic |
| Валидация | Pydantic v2 |
| HTTP-клиент | httpx, sync |
| Retry | tenacity |
| Планировщик | APScheduler, BackgroundScheduler |
| Тесты | pytest, pytest-cov, respx |
| Линтер | ruff |
| Пакеты | uv |
| Документация | OpenAPI + Swagger UI |

### Почему sync, а не async

- Один пользователь, SQLite, небольшие объемы данных.
- Синхронный SQLAlchemy проще и надежнее в связке с SQLite.
- FastAPI выполняет `def`-эндпоинты в threadpool, этого достаточно.
- MOEX-запросы синхронные через `httpx.Client`.
- Планировщик — `BackgroundScheduler`.
- Меньше шансов получить блокировки event loop и сложные ошибки.

### Точность вычислений

Деньги нельзя хранить в `float`.

- Суммы в рублях: `INTEGER` в копейках (`amount_kopecks`).
- Цены: `INTEGER` в миллионных долях рубля (`price_micro`, 6 знаков).
- Количество: `INTEGER`.
- Номинал облигации: `INTEGER` в копейках.
- В Python-коде — `Decimal`; округление `ROUND_HALF_UP`.
- В API деньги и цены отдаются строками с фиксированным количеством знаков:
  - суммы — `"1234.56"`;
  - цены — `"110.000000"`;
  - проценты — `"95.123000"`.

Пример:

```text
Цена 110.50 RUB       → price_micro = 110_500_000
Сумма 1234.56 RUB     → amount_kopecks = 123_456
Номинал 1000.00 RUB   → face_value_kopecks = 100_000
```

### Идентификация активов

- Акции: `engine=stock`, `market=shares`, `board=TQBR`.
- Облигации: `engine=stock`, `market=bonds`, `board=TQCB`.
- Уникальность: `(secid, board)`.
- Для MVP поддерживаются только бумаги с `primary_boardid` `TQBR` или `TQCB`.
- Остальные площадки отклоняются с понятной ошибкой.

## 3. Структура проекта

```text
backend/
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── .env.example
├── README.md
├── data/
│   ├── investments.db          # создается при запуске, gitignore
│   └── backups/                # резервные копии, gitignore
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, lifespan, routers
│   ├── core/
│   │   ├── config.py           # настройки из env
│   │   ├── logging.py
│   │   ├── errors.py           # AppError и коды
│   │   ├── periods.py          # допустимые периоды дашборда
│   │   └── time.py             # Europe/Moscow, UTC
│   ├── db/
│   │   ├── base.py             # DeclarativeBase, enum-типы
│   │   ├── session.py          # engine, SessionLocal, PRAGMA
│   │   ├── models/
│   │   │   ├── portfolio.py
│   │   │   ├── asset.py
│   │   │   ├── operation.py
│   │   │   ├── income.py
│   │   │   ├── quote.py
│   │   │   ├── bond.py
│   │   │   ├── snapshot.py
│   │   │   └── setting.py
│   │   └── migrations/         # alembic versions
│   ├── schemas/
│   │   ├── common.py
│   │   ├── portfolio.py
│   │   ├── asset.py
│   │   ├── operation.py
│   │   ├── position.py
│   │   ├── income.py
│   │   ├── dashboard.py
│   │   ├── snapshot.py
│   │   ├── quote.py
│   │   ├── settings.py
│   │   └── backup.py
│   ├── api/
│   │   ├── deps.py             # get_db, get_settings, get_moex
│   │   ├── router.py
│   │   └── routes/
│   │       ├── health.py
│   │       ├── portfolio.py
│   │       ├── assets.py
│   │       ├── operations.py
│   │       ├── positions.py
│   │       ├── income.py
│   │       ├── dashboard.py
│   │       ├── snapshots.py
│   │       ├── quotes.py
│   │       ├── settings.py
│   │       └── backup.py
│   ├── services/
│   │   ├── portfolio_service.py
│   │   ├── asset_service.py
│   │   ├── operation_service.py
│   │   ├── position_service.py
│   │   ├── income_service.py
│   │   ├── quote_service.py
│   │   ├── dashboard_service.py
│   │   ├── snapshot_service.py
│   │   ├── backup_service.py
│   │   └── settings_service.py
│   ├── providers/
│   │   └── moex/
│   │       ├── client.py
│   │       ├── schemas.py
│   │       ├── mapper.py
│   │       └── errors.py
│   ├── jobs/
│   │   ├── scheduler.py
│   │   └── refresh.py
│   └── scripts/
│       ├── seed_demo.py        # CLI: python -m app.scripts.seed_demo
│       └── backup.py           # CLI: python -m app.scripts.backup
└── tests/
    ├── conftest.py
    ├── *_helpers.py            # общие builders и API-хелперы
    ├── test_*.py               # unit, API и интеграционные тесты
    └── fixtures/
        └── moex/
```

### Правила структуры

- Роуты не содержат бизнес-логику: только валидация, вызов сервиса, преобразование ответа.
- Сервисы принимают `Session` и работают в транзакции.
- Провайдер MOEX не знает про БД и API.
- Схемы Pydantic отделены от ORM-моделей.
- Все настройки — через `app/core/config.py`.
- Ошибки — через `AppError`, единый формат ответа.
- MVP держит тесты плоским списком `test_*.py` рядом с общими хелперами и фикстурами; отдельные каталоги `unit/` и `integration/` не заводятся.

## 4. Конфигурация

Файл `.env.example`:

```env
APP_ENV=local
APP_VERSION=0.1.0

DATABASE_URL=sqlite:///./data/investments.db
DATA_DIR=./data
BACKUP_DIR=./data/backups

MOEX_BASE_URL=https://iss.moex.com/iss
MOEX_TIMEOUT_SECONDS=10
MOEX_RETRIES=3
MOEX_USER_AGENT=investment-tracker/0.1

QUOTE_REFRESH_ENABLED=true
QUOTE_REFRESH_HOUR=19
QUOTE_REFRESH_MINUTE=5
TIMEZONE=Europe/Moscow

CORS_ORIGINS=http://localhost:4200,http://127.0.0.1:4200
LOG_LEVEL=INFO
```

### SQLite PRAGMA

При подключении:

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
PRAGMA synchronous=NORMAL;
```

### Каталоги

- `data/` создается при старте.
- `data/backups/` создается при старте.
- Оба каталога в `.gitignore`.

## 5. Схема базы данных

### 5.1 `portfolio`

Одна запись, создается сидом.

| Поле | Тип | Ограничения |
|---|---|---|
| `id` | INTEGER | PK |
| `name` | VARCHAR(100) | NOT NULL, default «Мой портфель» |
| `base_currency` | CHAR(3) | NOT NULL, default RUB |
| `created_at` | DATETIME | NOT NULL, UTC |

### 5.2 `asset`

| Поле | Тип | Ограничения |
|---|---|---|
| `id` | INTEGER | PK |
| `secid` | VARCHAR(32) | NOT NULL |
| `isin` | VARCHAR(32) | NULL |
| `name` | VARCHAR(255) | NOT NULL |
| `short_name` | VARCHAR(100) | NULL |
| `type` | VARCHAR(10) | NOT NULL, `STOCK` / `BOND` |
| `engine` | VARCHAR(10) | NOT NULL, `stock` |
| `market` | VARCHAR(10) | NOT NULL, `shares` / `bonds` |
| `board` | VARCHAR(10) | NOT NULL, `TQBR` / `TQCB` |
| `currency` | CHAR(3) | NOT NULL, `RUB` |
| `initial_face_value_kopecks` | INTEGER | NULL, только облигации |
| `lot_size` | INTEGER | NOT NULL, default 1 |
| `is_active` | BOOLEAN | NOT NULL, default true |
| `metadata_json` | TEXT | NULL, сырые данные MOEX |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

Индексы и ограничения:

- `UNIQUE(secid, board)`.
- `INDEX(secid)`.
- `INDEX(type)`.

### 5.3 `operation`

| Поле | Тип | Ограничения |
|---|---|---|
| `id` | INTEGER | PK |
| `portfolio_id` | INTEGER | FK → portfolio.id, NOT NULL |
| `asset_id` | INTEGER | FK → asset.id, NOT NULL |
| `type` | VARCHAR(10) | NOT NULL, `BUY` / `SELL` |
| `trade_date` | DATE | NOT NULL |
| `quantity` | INTEGER | NOT NULL, CHECK > 0 |
| `price_micro` | INTEGER | NOT NULL, CHECK > 0, RUB за единицу |
| `input_price_micro` | INTEGER | NOT NULL, как ввел пользователь |
| `input_price_type` | VARCHAR(10) | NOT NULL, `RUB` / `PERCENT` |
| `face_value_kopecks` | INTEGER | NULL, номинал на дату операции |
| `note` | VARCHAR(500) | NULL |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

Индексы:

- `INDEX(portfolio_id, asset_id, trade_date, id)`.
- `INDEX(asset_id, trade_date)`.

Правила:

- Для акций `input_price_type` всегда `RUB`.
- Для облигаций допускаются `RUB` и `PERCENT`.
- `price_micro` всегда нормализованная цена в RUB за единицу.
- При вводе в процентах:
  `price_micro = round(face_value_kopecks / 100 × percent × 1_000_000)`.
- `face_value_kopecks` фиксируется на дату операции, чтобы история не менялась после амортизации.

### 5.4 `income`

| Поле | Тип | Ограничения |
|---|---|---|
| `id` | INTEGER | PK |
| `portfolio_id` | INTEGER | FK → portfolio.id, NOT NULL |
| `asset_id` | INTEGER | FK → asset.id, NOT NULL |
| `kind` | VARCHAR(10) | NOT NULL, `DIVIDEND` / `COUPON` |
| `status` | VARCHAR(10) | NOT NULL, `EXPECTED` / `PAID` |
| `amount_per_unit_micro` | INTEGER | NULL, RUB за единицу |
| `quantity` | INTEGER | NULL, количество на дату выплаты |
| `amount_total_kopecks` | INTEGER | NULL, итоговая сумма |
| `currency` | CHAR(3) | NOT NULL, `RUB` |
| `record_date` | DATE | NULL |
| `pay_date` | DATE | NOT NULL |
| `source` | VARCHAR(10) | NOT NULL, `MOEX` / `MANUAL` |
| `external_id` | VARCHAR(128) | NULL, уникальный |
| `note` | VARCHAR(500) | NULL |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

Индексы и ограничения:

- `UNIQUE(external_id)` — SQLite допускает несколько NULL.
- `INDEX(asset_id, status, pay_date)`.
- `INDEX(portfolio_id, kind, status)`.
- Проверка в сервисе: `EXPECTED` только для `COUPON`.
- Проверка в сервисе: `DIVIDEND` всегда `PAID`.

Правила:

- `EXPECTED` купон: `amount_per_unit_micro` заполнен, `quantity` и `amount_total_kopecks` могут быть NULL и вычисляются при чтении по текущему количеству.
- `PAID`: `quantity` и `amount_total_kopecks` заполнены, `amount_per_unit_micro` может быть NULL.
- `external_id` для MOEX: `moex:coupon:{secid}:{pay_date}`.
- При повторной синхронизации обновляются только `EXPECTED` записи; `PAID` не перезаписываются.

### 5.5 `quote`

| Поле | Тип | Ограничения |
|---|---|---|
| `id` | INTEGER | PK |
| `asset_id` | INTEGER | FK → asset.id, NOT NULL |
| `quote_date` | DATE | NOT NULL |
| `price_micro` | INTEGER | NOT NULL, CHECK > 0 |
| `price_type` | VARCHAR(10) | NOT NULL, `RUB` / `PERCENT` |
| `source` | VARCHAR(10) | NOT NULL, `MOEX` / `MANUAL` |
| `fetched_at` | DATETIME | NOT NULL |

Индексы и ограничения:

- `UNIQUE(asset_id, quote_date)`.
- `INDEX(asset_id, quote_date DESC)`.

Правила:

- Акции: `price_type=RUB`, `price_micro` — RUB за акцию.
- Облигации: `price_type=PERCENT`, `price_micro` — процент от номинала.
- Для одной даты одна цена; при обновлении — upsert.
- Ручная цена имеет приоритет? Нет: последняя запись по дате. Если пользователь ввел ручную цену на дату, MOEX-обновление не должно ее перезаписывать. Добавить правило: `source=MANUAL` не перезаписывается автоматически.

### 5.6 `bond_amortization`

| Поле | Тип | Ограничения |
|---|---|---|
| `id` | INTEGER | PK |
| `asset_id` | INTEGER | FK → asset.id, NOT NULL |
| `amortization_date` | DATE | NOT NULL |
| `amount_per_unit_kopecks` | INTEGER | NOT NULL, CHECK > 0 |
| `source` | VARCHAR(10) | NOT NULL, `MOEX` / `MANUAL` |
| `external_id` | VARCHAR(128) | NULL, уникальный |
| `created_at` | DATETIME | NOT NULL |

Индексы:

- `UNIQUE(external_id)`.
- `INDEX(asset_id, amortization_date)`.

Правила:

- Текущий номинал = `initial_face_value_kopecks − Σ(amount_per_unit_kopecks где date <= target_date)`, минимум 0.
- Для исторической стоимости используется номинал на дату.
- Полное погашение: если номинал стал 0, рыночная стоимость облигации 0. Для закрытия позиции пользователь вводит продажу/погашение вручную. Автоматический `REDEMPTION` в MVP не делаем.

### 5.7 `portfolio_snapshot`

| Поле | Тип | Ограничения |
|---|---|---|
| `id` | INTEGER | PK |
| `portfolio_id` | INTEGER | FK → portfolio.id, NOT NULL |
| `snapshot_date` | DATE | NOT NULL |
| `market_value_kopecks` | INTEGER | NOT NULL |
| `invested_kopecks` | INTEGER | NOT NULL |
| `income_paid_kopecks` | INTEGER | NOT NULL |
| `created_at` | DATETIME | NOT NULL |

Индексы:

- `UNIQUE(portfolio_id, snapshot_date)`.
- `INDEX(portfolio_id, snapshot_date DESC)`.

Назначение:

- Кэш дневной стоимости для истории и будущих отчетов.
- Основной график может считаться на лету; snapshot используется как быстрый источник и для ежедневного job.

### 5.8 `app_setting`

| Поле | Тип | Ограничения |
|---|---|---|
| `key` | VARCHAR(64) | PK |
| `value` | TEXT | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

Ключи:

- `last_quote_refresh_at`
- `last_quote_refresh_status`
- `quote_refresh_enabled`
- `dashboard_period`
- `schema_version` (служебный)

## 6. Бизнес-правила и расчеты

### 6.1 Восстановление позиции

Позиция не хранится в отдельной таблице. Она вычисляется из операций:

1. Загрузить все операции по активу, отсортированные по `trade_date`, `id`.
2. Пройти последовательно:
   - `BUY`: `qty += quantity`, `cost_kopecks += quantity × price_micro / 1_000_000 × 100`.
   - `SELL`: проверить `quantity <= qty`; `cost_kopecks -= avg_price × quantity`; `qty -= quantity`.
3. Если `qty = 0`: `avg = 0`, `cost = 0`.
4. Иначе `avg = cost_kopecks / 100 / qty`.

Текущее состояние (позиции, карточка актива, количество для ожидаемых купонов, итоги дашборда) считается на `today`: replay включает только операции с `trade_date <= today`, поэтому будущие сделки не меняют текущие значения. Валидация записи операций (§6.2) по-прежнему replay-ит всю историю, чтобы будущие сделки оставались допустимыми.

Округление:

- `cost_kopecks` — целое.
- При покупке сумма округляется до копейки `ROUND_HALF_UP`.
- При продаже списываемая стоимость округляется до копейки.
- Средняя цена для ответа — 6 знаков, `ROUND_HALF_UP`.
- Внутренние вычисления — `Decimal`, не `float`.

### 6.2 Валидация операций

При создании, изменении и удалении операции:

- Пересчитать всю историю операций актива.
- Если на любом шаге продажа превышает доступное количество — отклонить запрос `409 INSUFFICIENT_QUANTITY`.
- Нельзя продать больше, чем есть на дату операции с учетом предыдущих операций.
- `quantity > 0`, `price > 0`.
- `trade_date` — валидная дата; будущие даты разрешены, но UI может предупреждать.
- Удаление операции, после которого ломается последующая продажа, запрещено.

Пример:

```text
BUY  10 @ 100
BUY  10 @ 120
SELL 5  @ 150
```

Результат: 15 шт., средняя 110, себестоимость 1650 RUB.

### 6.3 Цена облигации

Ввод:

- `price_type=PERCENT`: пользователь вводит 95.123.
- `price_type=RUB`: пользователь вводит 951.23.

Нормализация:

```text
face_value_rub = face_value_kopecks / 100
price_rub = face_value_rub × percent / 100
price_micro = round(price_rub × 1_000_000)
```

Обратное отображение:

```text
percent = price_micro / 1_000_000 / face_value_rub × 100
```

Средняя цена покупки облигации в процентах:

```text
avg_price_percent = avg_price_rub / avg_purchase_face_rub × 100
```

- `avg_purchase_face_rub` — взвешенный номинал на даты покупок, который ведётся при replay позиции: каждая `BUY` добавляет `quantity × face_value_kopecks`, зафиксированный в операции.
- `SELL` списывает долю номинальной базы пропорционально количеству (округление `ROUND_HALF_UP`).
- Полное закрытие позиции сбрасывает номинальную базу в ноль.
- Fallback на текущий номинал — только для legacy-операций, где `face_value_kopecks` не сохранён.
- Поэтому `avg_price_percent` не меняется после амортизации и остаётся корректным для покупок, растянутых через дату амортизации.

### 6.4 Текущая стоимость

- Акция: `market_value = qty × price_rub`.
- Облигация: `market_value = qty × current_face_value_rub × price_percent / 100`.
- `current_face_value_rub` — номинал на текущую дату с учетом амортизации.
- Если цена отсутствует:
  - использовать последнюю цену с датой <= target_date;
  - если цен нет вообще — использовать среднюю цену (себестоимость) и вернуть `is_stale=true`, `price_source="COST"`.

### 6.5 Ожидаемые купоны

- Источник — MOEX `bondization`.
- При синхронизации создаются `EXPECTED` записи для купонов с `pay_date >= today`.
- Купоны в прошлом не создаются, чтобы не засорять список; пользователь добавляет фактические вручную.
- Сумма на текущий момент: `amount_per_unit × current_qty`, округление до копейки.
- Если `current_qty = 0`, купон показывается с суммой 0 или скрывается (решение: скрывать в дашборде, показывать в карточке актива).
- Просроченные `EXPECTED` (pay_date < today) возвращаются с `is_overdue=true`.

### 6.6 Фактические доходы

Дивиденд:

- Создается вручную.
- `kind=DIVIDEND`, `status=PAID`, `pay_date` обязательна, `amount_total` обязательна.
- `quantity` опциональна; если не указана — текущее количество.
- `amount_per_unit` опционален.

Купон:

- Может быть подтвержден из `EXPECTED` через `POST /api/income/{id}/mark-paid`.
- При подтверждении:
  - `status=PAID`;
  - `quantity = current_qty`;
  - `amount_total = переданная сумма` или расчетная;
  - `pay_date` можно изменить.
- Повторное подтверждение уже `PAID` — `409 INCOME_ALREADY_PAID`.
- Ручной фактический купон можно добавить без ожидаемой записи.

### 6.7 Дашборд

Итоги:

- `market_value` — сумма текущих стоимостей позиций.
- `invested` — сумма себестоимости открытых позиций.
- `dividends_paid` — сумма `PAID` с `kind=DIVIDEND`.
- `coupons_paid` — сумма `PAID` с `kind=COUPON`.
- `income_paid_total = dividends_paid + coupons_paid`.
- `expected_coupons` — сумма `EXPECTED` купонов с `current_qty > 0`.
- `positions_count`, `assets_count` (`assets_count` — все активы, включая закрытые позиции).

График:

- Периоды: `1M`, `3M`, `1Y`, `ALL`.
- Для каждой даты периода:
  - количество на дату — из операций;
  - цена — последняя известная цена <= даты;
  - стоимость — сумма по активам.
- Если по активу нет цены до даты, использовать себестоимость и пометить точку как частичную.
- Ответ содержит `series: [{date, market_value, invested, is_partial}]`; верхнеуровневый `is_partial=true`, если хотя бы одна точка ряда оценена по себестоимости.
- Ряд начинается с `max(начало периода, дата первой операции)`, а не с начала периода.
- `invested` на дату — себестоимость открытых позиций на дату.

Ближайшие купоны:

- `EXPECTED` купоны с `pay_date >= today` и текущим количеством > 0, сортировка `(pay_date, id)`.
- Просроченные купоны (`pay_date < today`) в список не попадают, но входят в итоговый `expected_coupons`.

### 6.8 Snapshot

- Ежедневный job после обновления котировок считает snapshot на сегодня. Шаг выполняется после успешного refresh; его сбой откатывается и логируется, не отменяя обновление котировок.
- Upsert по `(portfolio_id, snapshot_date)` (атомарный SQLite upsert, `created_at` сохраняется).
- `income_paid` суммируется по `PAID` доходам с `pay_date <= snapshot_date`.
- Используется для истории и диагностики; snapshots ограничены датой «сегодня».
- Dashboard может брать готовые snapshots, но при их отсутствии считает на лету.
- Диагностический `GET /api/snapshots?period=` возвращает сохранённые snapshots за период.

## 7. Интеграция с MOEX ISS

Базовый URL: `https://iss.moex.com/iss`.

### 7.1 Поиск бумаг

```http
GET /iss/securities.json?q={query}&iss.meta=off
```

Парсинг таблицы `securities`:

- `secid`
- `shortname`
- `name`
- `isin`
- `type`
- `primary_boardid`
- `is_traded`

Фильтры:

- `is_traded = 1`.
- `primary_boardid in (TQBR, TQCB)`.
- Типы: акции (`common_share`, `preferred_share`, `stock`) и облигации (`ofz_bond`, `corporate_bond`, `exchange_bond`, `bond`).
- Для MVP можно ориентироваться на board: `TQBR` → `STOCK`, `TQCB` → `BOND`.

Ответ API:

```json
{
  "items": [
    {
      "secid": "SBER",
      "isin": "RU0009029540",
      "name": "Сбербанк",
      "short_name": "Сбербанк",
      "type": "STOCK",
      "board": "TQBR",
      "currency": "RUB"
    }
  ]
}
```

### 7.2 Информация о бумаге

```http
GET /iss/securities/{secid}.json?iss.meta=off
```

Используемые поля:

- `SECNAME`, `SHORTNAME`, `ISIN`
- `FACEVALUE`, `FACEUNIT`
- `LOTSIZE`
- `BOARDID`
- `TYPE`

Для облигации `FACEVALUE` — номинал в RUB. Если пришел в другой валюте — отклонить (MVP только RUB).

### 7.3 Текущая цена

```http
GET /iss/engines/stock/markets/{market}/boards/{board}/securities/{secid}.json?iss.meta=off
```

Парсинг `marketdata`:

- `LAST`
- `LCURRENTPRICE`
- `MARKETPRICE`
- `PREVPRICE`

Правило выбора: первое положительное значение в порядке `LAST` → `LCURRENTPRICE` → `MARKETPRICE` → `PREVPRICE`.

Для облигаций значение — процент от номинала. Для акций — RUB.

### 7.4 История цен

```http
GET /iss/history/engines/stock/markets/{market}/boards/{board}/securities/{secid}.json
    ?from=YYYY-MM-DD&till=YYYY-MM-DD&start=0&iss.meta=off
```

Парсинг `history`:

- `TRADEDATE`
- `CLOSE`
- `LEGALCLOSEPRICE`

Правило: `CLOSE`, если положительный, иначе `LEGALCLOSEPRICE`.

Пагинация:

- MOEX отдает страницы (обычно 100 строк).
- Запрашивать `start += page_size`, пока страница непустая и меньше page_size.
- Ограничить глубину: не более 10 лет или от первой операции.

Кэш:

- Upsert в `quote` по `(asset_id, quote_date)`.
- Не перезаписывать `source=MANUAL`.

### 7.5 Купоны и амортизация

```http
GET /iss/securities/{secid}/bondization.json?iss.meta=off
```

Таблицы:

- `coupons`:
  - `coupondate`
  - `value` / `value_rub`
  - `valueprc`
  - `recorddate`
- `amortizations`:
  - `amortizationdate`
  - `value` / `value_rub`
  - `valueprc`

Маппинг:

- Купон: `amount_per_unit = value_rub` (RUB на одну облигацию), `pay_date = coupondate`, `record_date = recorddate`.
- Амортизация: `amount_per_unit = value_rub`, `date = amortizationdate`.

Если поля различаются между бумагами, маппер должен использовать fallback:

- `value_rub` → `value`;
- `coupondate` → `coupon_date`.

### 7.6 Ошибки и лимиты

- Таймаут 10 секунд.
- Retry 3 раза с экспоненциальной задержкой (0.5, 1, 2 сек).
- Не более 3 запросов в секунду.
- User-Agent обязателен.
- Ошибки:
  - `MOEX_UNAVAILABLE` — сеть/5xx/таймаут → HTTP 502.
  - `MOEX_NOT_FOUND` — 404/пустой ответ → HTTP 404.
  - `MOEX_PARSE_ERROR` — неожиданный формат → HTTP 502.
- При ошибке обновления приложение продолжает работать на кэше.

### 7.7 Синхронизация при добавлении актива

1. Запросить информацию о бумаге.
2. Создать `asset`.
3. Для облигации — запросить `bondization`, сохранить купоны и амортизацию.
4. Запросить текущую цену и историю за последний год.
5. Вернуть актив.

При повторном добавлении `(secid, board)` — `409 ASSET_ALREADY_EXISTS`.

## 8. API-контракт

Базовый префикс: `/api`.
Формат: JSON, UTF-8.
Даты: `YYYY-MM-DD`.
Время: ISO 8601 с таймзоной.
Деньги и цены: строки.

### 8.1 Служебные

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/health` | Статус приложения, БД, MOEX, последнее обновление |
| `GET` | `/api/openapi.json` | OpenAPI-схема (штатно у FastAPI `/openapi.json`) |
| `GET` | `/docs` | Swagger UI |

`GET /api/health`:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "ok",
  "moex": "ok",
  "last_quote_refresh_at": "2026-10-19T19:05:00+03:00"
}
```

### 8.2 Портфель

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/portfolio` | Получить единственный портфель |
| `PATCH` | `/api/portfolio` | Переименовать портфель |

`GET /api/portfolio`:

```json
{
  "id": 1,
  "name": "Мой портфель",
  "base_currency": "RUB",
  "created_at": "2026-10-19T12:00:00Z"
}
```

### 8.3 Активы

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/assets` | Локальные активы |
| `GET` | `/api/assets/search?q=SBER` | Поиск в MOEX |
| `POST` | `/api/assets` | Добавить бумагу из MOEX |
| `GET` | `/api/assets/{id}` | Карточка актива |
| `POST` | `/api/assets/{id}/refresh` | Обновить метаданные, купоны, амортизацию |
| `DELETE` | `/api/assets/{id}` | Удалить, если нет операций и доходов |

`GET /api/assets/search?q=SBER`:

```json
{
  "items": [
    {
      "secid": "SBER",
      "isin": "RU0009029540",
      "name": "Сбербанк",
      "short_name": "Сбербанк",
      "type": "STOCK",
      "board": "TQBR",
      "currency": "RUB"
    }
  ]
}
```

`POST /api/assets`:

```json
{
  "secid": "SBER",
  "board": "TQBR"
}
```

Ответ `201`:

```json
{
  "id": 1,
  "secid": "SBER",
  "isin": "RU0009029540",
  "name": "Сбербанк",
  "short_name": "Сбербанк",
  "type": "STOCK",
  "board": "TQBR",
  "currency": "RUB",
  "initial_face_value": null,
  "lot_size": 10,
  "is_active": true
}
```

`GET /api/assets/{id}`:

```json
{
  "id": 2,
  "secid": "SU26238RMFS4",
  "isin": "RU000A0JX0J2",
  "name": "ОФЗ 26238",
  "short_name": "ОФЗ 26238",
  "type": "BOND",
  "board": "TQCB",
  "currency": "RUB",
  "initial_face_value": "1000.00",
  "current_face_value": "1000.00",
  "lot_size": 1,
  "is_active": true,
  "amortizations": []
}
```

### 8.4 Операции

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/operations?asset_id=&from=&to=` | Список операций |
| `POST` | `/api/operations` | Создать операцию |
| `PATCH` | `/api/operations/{id}` | Изменить операцию |
| `DELETE` | `/api/operations/{id}` | Удалить операцию |

`POST /api/operations`:

```json
{
  "asset_id": 1,
  "type": "BUY",
  "trade_date": "2026-01-10",
  "quantity": 10,
  "price": "100.00",
  "price_type": "RUB",
  "note": "Первая покупка"
}
```

Для облигации:

```json
{
  "asset_id": 2,
  "type": "BUY",
  "trade_date": "2026-02-01",
  "quantity": 15,
  "price": "95.123",
  "price_type": "PERCENT",
  "note": null
}
```

Ответ `201`:

```json
{
  "id": 1,
  "asset_id": 1,
  "type": "BUY",
  "trade_date": "2026-01-10",
  "quantity": 10,
  "input_price": "100.000000",
  "input_price_type": "RUB",
  "price_rub": "100.000000",
  "note": "Первая покупка"
}
```

Ошибки:

- `409 INSUFFICIENT_QUANTITY` — продажа больше остатка.
- `404 ASSET_NOT_FOUND`.
- `422 VALIDATION_ERROR`.

### 8.5 Позиции

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/positions` | Позиции с количеством, средней, стоимостью |

Ответ:

```json
{
  "items": [
    {
      "asset": {
        "id": 1,
        "secid": "SBER",
        "name": "Сбербанк",
        "type": "STOCK"
      },
      "quantity": 20,
      "avg_price": "110.000000",
      "avg_price_percent": null,
      "current_price": "310.500000",
      "current_price_type": "RUB",
      "current_face_value": null,
      "market_value": "6210.00",
      "invested": "2200.00",
      "share": "0.1532",
      "price_date": "2026-10-19",
      "price_source": "MOEX",
      "is_stale": false
    }
  ],
  "total_market_value": "6210.00",
  "total_invested": "2200.00"
}
```

Для облигации:

```json
{
  "asset": {
    "id": 2,
    "secid": "SU26238RMFS4",
    "name": "ОФЗ 26238",
    "type": "BOND"
  },
  "quantity": 15,
  "avg_price": "951.230000",
  "avg_price_percent": "95.123000",
  "current_price": "98.500000",
  "current_price_type": "PERCENT",
  "current_face_value": "1000.00",
  "market_value": "14775.00",
  "invested": "14268.45",
  "share": "0.3645",
  "price_date": "2026-10-19",
  "price_source": "MOEX",
  "is_stale": false
}
```

`avg_price_percent` считается от взвешенного номинала на даты покупок (§6.3),
поэтому после амортизации он остаётся равным проценту покупки (в примере —
`95.123000`), а не пересчитывается от текущего номинала.

### 8.6 Доходы

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/income?status=&kind=&asset_id=&from=&to=` | Список доходов |
| `POST` | `/api/income` | Добавить фактический дивиденд/купон |
| `PATCH` | `/api/income/{id}` | Изменить запись |
| `POST` | `/api/income/{id}/mark-paid` | Подтвердить ожидаемый купон |
| `DELETE` | `/api/income/{id}` | Удалить запись |

`GET /api/income?status=PAID`:

```json
{
  "items": [
    {
      "id": 1,
      "asset_id": 1,
      "asset_secid": "SBER",
      "kind": "DIVIDEND",
      "status": "PAID",
      "amount_per_unit": "10.00",
      "quantity": 20,
      "amount_total": "200.00",
      "currency": "RUB",
      "record_date": null,
      "pay_date": "2026-07-15",
      "source": "MANUAL",
      "is_overdue": false
    }
  ],
  "totals": {
    "dividends_paid": "200.00",
    "coupons_paid": "0.00",
    "expected_coupons": "525.00"
  }
}
```

`POST /api/income` (фактический дивиденд):

```json
{
  "asset_id": 1,
  "kind": "DIVIDEND",
  "amount_total": "200.00",
  "pay_date": "2026-07-15",
  "quantity": 20,
  "amount_per_unit": "10.00",
  "note": "Выплата за 2025 год"
}
```

`POST /api/income/{id}/mark-paid`:

```json
{
  "amount_total": "525.00",
  "pay_date": "2026-12-15"
}
```

### 8.7 Дашборд

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/dashboard?period=1Y` | Итоги, позиции, график, ближайшие купоны |
| `GET` | `/api/snapshots?period=1Y` | Сохранённые дневные snapshot-ы за период (диагностика) |

Неподдерживаемый `period` → `422` (валидация query-параметра).

Ответ:

```json
{
  "as_of": "2026-10-19",
  "currency": "RUB",
  "period": "1Y",
  "totals": {
    "market_value": "20985.00",
    "invested": "16468.45",
    "dividends_paid": "200.00",
    "coupons_paid": "525.00",
    "income_paid_total": "725.00",
    "expected_coupons": "525.00",
    "positions_count": 2,
    "assets_count": 3
  },
  "series": [
    {
      "date": "2026-01-10",
      "market_value": "1000.00",
      "invested": "1000.00",
      "is_partial": false
    },
    {
      "date": "2026-01-11",
      "market_value": "1010.00",
      "invested": "1000.00",
      "is_partial": false
    }
  ],
  "positions": [],
  "upcoming_coupons": [],
  "is_partial": false
}
```

`GET /api/snapshots?period=1Y`:

```json
{
  "period": "1Y",
  "items": [
    {
      "date": "2026-10-19",
      "market_value": "20985.00",
      "invested": "16468.45",
      "income_paid": "725.00"
    }
  ]
}
```

### 8.8 Котировки

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/quotes/{asset_id}/history?period=1Y` | История цен актива |
| `POST` | `/api/quotes/refresh` | Обновить все котировки |
| `POST` | `/api/quotes/manual` | Добавить ручную цену |

`POST /api/quotes/refresh`:

```json
{
  "updated": 2,
  "failed": 0,
  "last_refresh_at": "2026-10-19T19:05:00+03:00",
  "errors": []
}
```

`POST /api/quotes/manual`:

```json
{
  "asset_id": 1,
  "quote_date": "2026-10-18",
  "price": "305.50",
  "price_type": "RUB"
}
```

### 8.9 Настройки

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/settings` | Эффективные настройки |
| `PATCH` | `/api/settings` | Изменить разрешенные ключи |

Разрешенные ключи:

- `quote_refresh_enabled`
- `dashboard_period`

`GET /api/settings`:

```json
{
  "quote_refresh_enabled": true,
  "dashboard_period": "1Y"
}
```

`PATCH /api/settings` — можно передать один или оба ключа:

```json
{
  "quote_refresh_enabled": true,
  "dashboard_period": "3M"
}
```

Правила:

- `GET` возвращает эффективные значения: `quote_refresh_enabled` учитывает env-master-switch, `dashboard_period` — сохранённую настройку или `1Y`.
- `PATCH` обновляет только переданные ключи и возвращает полный набор эффективных значений; непереданные ключи не меняются.
- Неизвестный ключ, `null`, пустой payload или невалидный период/boolean → `422 VALIDATION_ERROR`.
- `PATCH` с `quote_refresh_enabled=true` при `QUOTE_REFRESH_ENABLED=false` → `400 BAD_REQUEST`: настройка развёртывания имеет приоритет.
- `QUOTE_REFRESH_ENABLED=false` — master switch: scheduler не создаётся, автоматические обновления выключены. При `true` сохранённая настройка включает/выключает плановые запуски, пока scheduler существует. Ручной `POST /api/quotes/refresh` от этих настроек не зависит.
- `GET /api/dashboard` без `period` использует сохранённый `dashboard_period` (по умолчанию `1Y`); явный query-параметр переопределяет его.

### 8.10 Backup и export

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/api/backup` | Создать копию SQLite |
| `GET` | `/api/export?format=json` | Экспорт JSON (по умолчанию) |
| `GET` | `/api/export?format=csv` | ZIP с CSV: позиции, операции, доходы |

`POST /api/backup`:

```json
{
  "path": "data/backups/investments-20261019-190500.db",
  "size_bytes": 245760,
  "created_at": "2026-10-19T19:05:00+03:00"
}
```

Правила backup:

- Копия создаётся через SQLite backup API, поэтому WAL-содержимое попадает в файл; обычное копирование файла для этого не используется.
- Источник открывается read-only и проверяется: файл должен существовать, быть непустым и содержать схему приложения (таблицу `portfolio`).
- Имя — `investments-YYYYMMDD-HHMMSS.db` в локальном времени; при совпадении добавляется суффикс `-1`, `-2` и т. д.
- Одновременные копии в процессе сериализуются; при ошибке частично созданный файл удаляется.
- В ответе путь в POSIX-формате (`data/backups/...`).
- Ошибки: `400 BAD_REQUEST` для отсутствующего/пустого/немигрированного файла или не-SQLite источника; `500 INTERNAL_ERROR` для сбоя копирования без утечки путей и деталей драйвера.
- Backup-файлы не отдаются по HTTP: доступен только путь в ответе.
- `POST /api/backup` возвращает `200` (не `201`).

`GET /api/export?format=json` (формат по умолчанию):

- `Content-Type: application/json`, `Content-Disposition: attachment; filename="investments-export-YYYYMMDD-HHMMSS.json"`.
- Ключи: `exported_at`, `app_version`, `portfolio`, `assets`, `operations`, `income`, `quotes`, `amortizations`, `snapshots`, `settings`.
- Деньги и даты — строки, как в API; это человекочитаемая проекция, а не lossless-формат восстановления. Каноническая резервная копия — SQLite-файл из `POST /api/backup`.

`GET /api/export?format=csv`:

- `Content-Type: application/zip`, `Content-Disposition: attachment; filename="investments-export-YYYYMMDD-HHMMSS.zip"`.
- В архиве ровно три файла: `positions.csv`, `operations.csv`, `income.csv`.
- CSV — UTF-8 с BOM, окончания строк CRLF; значения, начинающиеся с `=`, `+`, `-`, `@`, табуляции или CR, экранируются как текст для защиты от формул.
- Orphan-строки (операции/доходы без актива) сохраняются в экспорте.

Невалидный `format` (не `json`/`csv`) → `422 VALIDATION_ERROR`.

### 8.11 Формат ошибок

Все ошибки:

```json
{
  "error": {
    "code": "INSUFFICIENT_QUANTITY",
    "message": "Нельзя продать 20: доступно 15",
    "details": {
      "asset_id": 1,
      "available": 15,
      "requested": 20
    }
  }
}
```

Коды:

| HTTP | Код | Когда |
|---|---|---|
| 400 | `BAD_REQUEST` | Некорректный запрос |
| 404 | `NOT_FOUND` | Объект не найден |
| 404 | `ASSET_NOT_FOUND` | Актив не найден |
| 409 | `ASSET_ALREADY_EXISTS` | Дубликат актива |
| 409 | `ASSET_IN_USE` | Удаление актива с операциями |
| 409 | `INSUFFICIENT_QUANTITY` | Продажа больше остатка |
| 409 | `INCOME_ALREADY_PAID` | Повторное подтверждение |
| 422 | `VALIDATION_ERROR` | Ошибка Pydantic |
| 502 | `MOEX_UNAVAILABLE` | MOEX недоступен |
| 502 | `MOEX_PARSE_ERROR` | Неожиданный ответ MOEX |
| 500 | `INTERNAL_ERROR` | Непредвиденная ошибка |

## 9. Сервисы и модули

### `PositionService`

- `get_positions(portfolio_id) -> list[Position]`
- `get_position(asset_id) -> Position`
- `validate_operation_sequence(asset_id)`
- `calculate_position(operations) -> PositionState`
- `average_price`, `cost_basis`, `market_value`
- Не пишет в БД, кроме чтения.

### `OperationService`

- `list`, `create`, `update`, `delete`.
- При изменении/удалении — пересчет и валидация всей истории.
- Нормализация цены облигации.
- Проверка `asset_id`, типа актива.

### `AssetService`

- `search_moex(query)`
- `create_from_moex(secid, board)`
- `get`, `list`, `delete`
- `refresh_metadata`
- Синхронизация купонов и амортизации для облигаций.

### `IncomeService`

- `list`, `create_manual`, `update`, `delete`.
- `sync_coupons(asset)` — upsert EXPECTED.
- `mark_paid`.
- `totals(portfolio_id)`.
- `expected_amount(income, current_qty)`.

### `QuoteService`

- `refresh_all()`
- `refresh_asset(asset)`
- `backfill_history(asset, from_date)`
- `get_history(asset_id, period)`
- `get_last_quote(asset_id, on_date=None)`
- `add_manual`.
- Upsert с защитой `MANUAL`.

### `DashboardService`

- `get_dashboard(period)`.
- Собирает позиции, итоги, серию, ближайшие купоны.
- Использует `PositionService`, `IncomeService`, `QuoteService`.

### `SnapshotService`

- `compute_for_date(date)`.
- `upsert_snapshot`.
- `get_snapshots(period)`.

### `BackupService`

- `create_backup()` — WAL-safe копия SQLite через backup API.
  - Источник read-only; проверки существования, непустого файла и схемы `portfolio`.
  - Локальное имя `investments-YYYYMMDD-HHMMSS.db`, суффикс при коллизии, thread lock, удаление частичного файла.
  - Возвращает `path`, `size_bytes`, `created_at`; путь в POSIX-формате.
- `export_json(session)` — проекция API (portfolio, assets, operations, income, quotes, amortizations, snapshots, settings) с деньгами/датами строками.
  - Не lossless-формат восстановления; каноническая копия — SQLite-файл.
- `export_csv_zip(session)` — ZIP с `positions.csv`, `operations.csv`, `income.csv`; UTF-8 BOM, CRLF, санитизация формул, orphan-строки сохраняются.

### `MoexClient`

- `search_securities(query)`.
- `get_security(secid)`.
- `get_current_quote(asset)`.
- `get_history(asset, from_date, till_date)`.
- `get_bondization(secid)`.
- Внутри: retry, timeout, rate limit, парсинг.
- Не работает с БД.

### `SettingsService`

- `get_value`, `set_value`.
- `all_values` — все сохранённые настройки для экспорта; ошибки БД пробрасываются.
- `get_quote_refresh_enabled` / `set_quote_refresh_enabled` — толерантный разбор boolean.
- `effective_quote_refresh_enabled(env_enabled)` — env-master-switch AND сохранённая настройка.
- `get_dashboard_period` / `set_dashboard_period` — период из `app/core/periods.py`, невалидный отклоняется.
- `get_last_quote_refresh_at` / `set_last_quote_refresh` — время и статус последнего refresh (naive UTC).

## 10. Фоновые задачи и жизненный цикл

### Startup (`lifespan`)

1. Создать каталоги `data/`, `data/backups/`.
2. Применить миграции? В dev — да, в prod — отдельной командой. Для простоты local — `alembic upgrade head` в стартовом скрипте, не в коде.
3. Проверить/создать единственный портфель.
4. Инициализировать планировщик.
5. Запустить фоновое обновление котировок с задержкой 5–10 секунд, чтобы не блокировать старт.
6. Логировать версию и путь к БД.

### Ежедневный job

- Время: 19:05 Europe/Moscow (после закрытия основной сессии).
- Перед обновлением job проверяет эффективный флаг: env `QUOTE_REFRESH_ENABLED` AND сохранённый `quote_refresh_enabled`. Если автоматическое обновление выключено, плановый запуск пропускается без сетевых запросов; ручной `POST /api/quotes/refresh` это не затрагивает.
- Шаги:
  1. Взять lock.
  2. Обновить текущие котировки всех активных активов.
  3. Дозагрузить историю с последней даты.
  4. Синхронизировать купоны/амортизацию облигаций.
  5. Посчитать snapshot на сегодня.
  6. Записать `last_quote_refresh_at` и статус.
  7. Освободить lock.
- Ошибка одного актива не должна ломать весь job; собирать `errors[]`.

### Ручное обновление

- `POST /api/quotes/refresh` использует тот же сервис.
- Если job уже выполняется — `409 REFRESH_IN_PROGRESS` или дождаться? Для MVP: `409` с сообщением.

### Lock

- `threading.Lock` в процессе.
- При нескольких процессах не защищает; для local одного процесса достаточно.

### Shutdown

- Остановить планировщик.
- Закрыть HTTP-клиент.
- Закрыть engine.

## 11. Ошибки, логирование, безопасность

### Логирование

- Стандартный `logging` + JSON-формат в prod.
- Уровни: INFO для старта/job, WARNING для MOEX-ошибок, ERROR для 5xx.
- Не логировать полные ответы MOEX.
- В каждом запросе — `request_id` (middleware).

### Безопасность

- Слушать `127.0.0.1` по умолчанию.
- CORS только для localhost:4200.
- CORS отдаёт наружу заголовок `Content-Disposition`, чтобы frontend мог прочитать имя файла экспорта.
- Нет авторизации в MVP.
- Валидация всех входных данных Pydantic.
- SQL только через SQLAlchemy.
- Не отдавать stack trace в API.
- Backup-файлы не доступны по HTTP; только путь в ответе.

### Ограничения

- SQLite и один процесс.
- Нет конкурентных пользователей.
- Нет шифрования БД.

## 12. Тестирование

### Unit

- Средняя цена: 10@100 + 10@120 = 20@110.
- Продажа: 5@150 → 15@110, cost 1650.
- Продажа больше остатка → ошибка.
- Backdated buy/sell и пересчет.
- Конвертация облигации: 1000 × 95.123% = 951.23.
- Номинал с амортизацией: 1000 − 200 = 800.
- Ожидаемый купон: 35 × 15 = 525.
- Округление до копейки.
- Dashboard series: количество на дату, последняя цена.
- Fallback на себестоимость при отсутствии цены.
- Dashboard totals: открытые позиции, выплаты, ожидаемые купоны, `assets_count`.
- Snapshot: расчёт/идемпотентный upsert, период и верхняя граница «сегодня».
- Будущие операции не меняют текущие позиции/итоги, но участвуют в валидации записи.
- Границы «сегодня»: `pay_date == today` и операции/котировки/амортизация на текущую дату.
- SettingsService: boolean-алиасы и default, валидация периода, `all_values`, effective-флаг с env-master-switch.
- BackupService: WAL-safe копия, read-only источник, отсутствующий/пустой/немигрированный/повреждённый файл, конкурентные имена, cleanup частичного файла, CLI.
- Export: JSON-ключи и строковые деньги, CSV-файлы/порядок/пустая БД/orphan-строки/санитизация формул, BOM и CRLF.
- Settings job gate: выключенный env-master-switch или сохранённый флаг пропускает плановый refresh; ручной refresh не блокируется.

### Provider (MOEX)

- Поиск: парсинг `securities`.
- Информация: `FACEVALUE`, `LOTSIZE`, `ISIN`.
- Текущая цена: приоритет `LAST` → `LCURRENTPRICE` → `MARKETPRICE`.
- История: пагинация, `CLOSE`/`LEGALCLOSEPRICE`.
- Bondization: купоны, амортизация.
- Ошибки: timeout, 500, пустой ответ.
- Использовать `respx` и JSON-фикстуры, без реальной сети.

### Integration

- Миграции на чистой SQLite.
- CRUD активов.
- CRUD операций + пересчет.
- Подтверждение купона.
- Ручной дивиденд.
- Dashboard.
- Snapshots.
- Backup/export.
- Удаление актива с операциями → 409.
- Повторное добавление актива → 409.
- Seed demo: офлайн-идемпотентность, частичное восстановление, откат при сбое, невалидный якорь, точный состав демо-данных.
- Acceptance: демо-подмножество §14 — health, позиции, процент облигации, дашборд, доходы/snapshots, backup, JSON/CSV-экспорт, oversell 409.

### API

- `TestClient` + temporary SQLite.
- Проверка кодов и формата ошибок.
- Проверка строковых денег.
- Проверка OpenAPI generation.
- Настройки: defaults, частичный PATCH, 422 для unknown/null/empty/invalid, 400 при PATCH `true` под env `false`.
- Backup/export: content types, `Content-Disposition`, имена файлов, ZIP-состав, 422 для невалидного `format`.
- OpenAPI-контракт: все документированные пути/методы, уникальные `operationId`, ключевые схемы, деньги-строки, enum-ы, `additionalProperties: false`.

### Coverage

- Цель: не менее 80% для `services/` и `providers/`.
- `pytest --cov=app --cov-report=term-missing`.

## 13. Этапы реализации

| Этап | Работы | Результат | Оценка |
|---|---|---|---|
| 0 | Каркас `backend/`, `pyproject.toml`, настройки, логирование, health | Приложение запускается, `/api/health` работает | 0.5 дня |
| 1 | Модели, Alembic, SQLite PRAGMA, seed портфеля | Миграции применяются, таблицы созданы | 0.5–1 день |
| 2 | MOEX client: поиск, инфо, котировка, история, bondization | Провайдер с тестами на фикстурах | 1–1.5 дня |
| 3 | AssetService + API активов | Поиск и добавление SBER/ОФЗ | 0.5–1 день |
| 4 | OperationService + PositionService + API | Покупка/продажа, средняя, валидация | 1–1.5 дня |
| 5 | IncomeService: купоны, амортизация, mark-paid, дивиденды | Учет доходов | 1–1.5 дня |
| 6 | QuoteService: refresh, history, manual, scheduler | Автоцены и история | 1 день |
| 7 | DashboardService + snapshots | Итоги и график | 1 день |
| 8 | Settings, backup, export | Данные можно сохранить | 0.5 дня |
| 9 | Тесты, OpenAPI, README, seed demo | Backend готов к передаче | 1 день |

**Итого: 7–9 рабочих дней.**
Минимальный backend для frontend (этапы 0–4): **3–4 дня**.

### Вехи

- **M1 (0.5–1 день):** запуск, БД, health.
- **M2 (2–2.5 дня):** MOEX + активы.
- **M3 (3–4 дня):** операции + позиции.
- **M4 (5–6 дней):** доходы + котировки.
- **M5 (6–7 дней):** дашборд + backup.
- **M6 (7–9 дней):** тесты + документация + handoff.

## 14. Критерии готовности

### Функциональные

- `GET /api/health` возвращает `ok`.
- Поиск «SBER» находит акцию; добавление создает актив.
- Покупка 10@100 и 10@120 → 20 шт., средняя 110.
- Продажа 5@150 → 15 шт., средняя 110.
- Продажа больше остатка → 409.
- Облигация 1000 @ 95% → средняя 950 RUB, отображается 95%.
- Ожидаемый купон создается из MOEX.
- Подтверждение купона переводит в PAID с суммой.
- Ручной дивиденд попадает в выплаченный доход.
- Дашборд отдает итоги, позиции, серию, ближайшие купоны.
- История цен загружается и используется в графике.
- Backup и export создают файлы.

### Технические

- `uv run alembic upgrade head` работает на чистой БД.
- `uv run pytest` — green.
- `uv run ruff check .` — без ошибок.
- OpenAPI доступен, схемы валидны.
- Приложение запускается одной командой.
- При недоступности MOEX API не падает.
- Нет `float` в денежных расчетах.
- Все даты и таймзоны корректны.
- README описывает запуск, env, seed, тесты.

## 15. Передача frontend

### Что получает frontend

- Base URL: `http://127.0.0.1:8000/api`.
- Swagger UI: `http://127.0.0.1:8000/docs`.
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`.
- CORS для `http://localhost:4200`.
- Демо-данные: `uv run python -m app.scripts.seed_demo`.
- Примеры запросов в этом документе.

### Генерация клиента

Вариант 1 — типы:

```bash
npx openapi-typescript http://127.0.0.1:8000/openapi.json -o src/app/api/schema.ts
```

Вариант 2 — Angular-клиент:

```bash
npx @openapitools/openapi-generator-cli generate \
  -i http://127.0.0.1:8000/openapi.json \
  -g typescript-angular \
  -o src/app/api/generated
```

### Договоренности

- Frontend не обращается к MOEX напрямую.
- Все деньги/цены — строки; frontend форматирует.
- Даты — `YYYY-MM-DD`.
- Ошибки — единый формат `error.code`.
- Изменения API — через обновление этого документа и версии.

### Демо-данные

Seed создает:

- портфель «Мой портфель»;
- SBER: 2 покупки, 1 продажа;
- ОФЗ: покупка, купоны, амортизация;
- несколько котировок за период;
- фактические дивиденды и купоны;
- ожидаемые купоны.

Это позволяет frontend работать без сети и MOEX.

Seed офлайн и идемпотентен: версия и дата-якорь хранятся в `app_setting`
(`demo_seed_version`, `demo_seed_anchor`), повторный запуск не дублирует и не
сдвигает данные, а прерванный запуск можно безопасно повторить.

## 16. Риски и ограничения

| Риск | Мера |
|---|---|
| MOEX меняет поля ISS | Фикстуры, mapper с fallback, тесты |
| MOEX недоступен | Кэш в SQLite, retry, статус в health |
| Будущие дивиденды не поддерживаются | В MVP только фактические |
| НКД не учитывается | Средняя цена чистая; задокументировано |
| Полное погашение облигации | Ручная продажа/закрытие позиции |
| Сплиты акций | Ручная корректировка операции |
| SQLite и конкурентные записи | Один пользователь, WAL, busy_timeout |
| Долгая история цен | Пагинация, ограничение глубины, кэш |
| Ошибка в расчете средней | Unit-тесты, Decimal, replay операций |
| Удаление операции ломает историю | Полный replay и запрет |
| API меняется после начала frontend | Заморозка контракта после M3, версионирование |
| Локальный доступ без пароля | Только 127.0.0.1 |

## 17. Команды запуска

### Установка

```bash
cd backend
uv sync
cp .env.example .env
```

### Миграции

```bash
uv run alembic upgrade head
```

### Запуск

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Swagger

```text
http://127.0.0.1:8000/docs
```

### Демо-данные

```bash
uv run python -m app.scripts.seed_demo
```

### Тесты

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
```

### Линтер

```bash
uv run ruff check .
uv run ruff format --check .
```

### Проверка миграций на чистой БД

```bash
rm -f data/investments.db
uv run alembic upgrade head
```

### Резервная копия вручную

```bash
uv run python -m app.scripts.backup
```

---

## Итог

Backend реализуется первым и заканчивается стабильным REST API, базой, расчетами, MOEX-интеграцией, тестами и демо-данными. Frontend после этого работает только с `/api`, не зная про SQLite и MOEX. Такой порядок позволяет заморозить контракт и не переписывать UI при изменении внутренней реализации.

---

## Статус реализации

Отметки о выполнении этапов. Детали и результаты ревью — в [`BACKEND_PROGRESS.md`](BACKEND_PROGRESS.md).

Все этапы 0–9 выполнены; backend готов к передаче frontend.

- [x] Этап 0. Каркас, конфигурация, логирование, health
- [x] Этап 1. Модели, Alembic, SQLite PRAGMA, seed портфеля
- [x] Этап 2. MOEX client: поиск, инфо, котировка, история, bondization
- [x] Этап 3. AssetService + API активов
- [x] Этап 4. OperationService + PositionService + API
- [x] Этап 5. IncomeService: купоны, амортизация, mark-paid, дивиденды
- [x] Этап 6. QuoteService: refresh, history, manual, scheduler
- [x] Этап 7. DashboardService + snapshots
- [x] Этап 8. Settings, backup, export
- [x] Этап 9. Тесты, OpenAPI, README, seed demo

