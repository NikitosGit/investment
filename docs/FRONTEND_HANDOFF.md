# Frontend handoff — API «Учет инвестиций»

- **Версия:** 1.0
- **Дата:** 2026-10-30
- **Статус:** backend заморожен, контракт передан frontend
- **Источники:** `PLAN.md` §1–14, `docs/BACKEND_PLAN.md` §8/§8.9/§8.10/§11/§15, фактический OpenAPI и ответы временной seeded-БД
- **Связанный документ:** [`FRONTEND_PLAN.md`](FRONTEND_PLAN.md)

## 1. Назначение и границы

Frontend — Angular-приложение для одного локального портфеля. Оно работает **только с `/api`** и не обращается к MOEX напрямую.

- Один пользователь, один портфель, валюта RUB.
- Нет авторизации, токенов и ролей.
- Нет бизнес-расчётов на клиенте: средняя цена, стоимость, доли, купоны и итоги приходят с backend.
- Backend слушает `127.0.0.1`; приложение не предназначено для публикации в сеть без отдельной проработки безопасности.
- Контракт API считается замороженным. Любое изменение — только через новую версию OpenAPI и согласование. На этапе production допускается только добавление раздачи статики/SPA fallback в FastAPI без изменения `/api`.

## 2. Запуск backend

### 2.1. Требования

- Python 3.12.
- `uv`.
- Node.js **24.22** (проверено; Angular 20 официально поддерживает Node 20.19+/22.12+/24.x) и npm — только для frontend.
- Frontend-стек запинен: Angular **20.3.34** (CLI/build **20.3.42**, builder `@angular/build:application`), PrimeNG **20.4.0** (MIT), `@primeuix/themes` **2.0.0** (MIT, Aura), PrimeIcons 7.0.0, Chart.js 4.4.9, TypeScript 5.9.3, RxJS 7.8.2, Zone.js 0.15.1. Тесты — Karma + Jasmine через `@angular/build:karma`: `npm test -- --watch=false --browsers=ChromeHeadless` с `CHROME_BIN`.

### 2.2. Установка и миграции

```powershell
cd backend
uv sync
Copy-Item .env.example .env
uv run alembic upgrade head
```

Если `uv` не найден в `PATH`, используйте `python -m uv`:

```powershell
python -m uv sync
python -m uv run alembic upgrade head
```

### 2.3. Запуск

```powershell
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Или без `uv` в `PATH`:

```powershell
python -m uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Если venv уже активирован (`.venv\Scripts\Activate.ps1`), можно запускать `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`; зависимости всё равно ставятся через `uv sync` в `backend`.

### 2.4. Демо-данные

```powershell
cd backend
uv run python -m app.scripts.seed_demo
```

Seed офлайн-идемпотентен: повторный запуск не дублирует и не сдвигает данные. Требуется уже применённая схема БД. Если `uv` не в `PATH`: `python -m uv run python -m app.scripts.seed_demo`.

### 2.5. URL и CORS

| Что | Адрес |
|---|---|
| API | `http://127.0.0.1:8000/api` |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| OpenAPI JSON | `http://127.0.0.1:8000/openapi.json` |
| Health | `http://127.0.0.1:8000/api/health` |

- OpenAPI доступен **только** по `/openapi.json`, не по `/api/openapi.json`.
- CORS по умолчанию: `http://localhost:4200` и `http://127.0.0.1:4200`.
- CORS отдаёт наружу `Content-Disposition` и `X-Request-ID`.
- Авторизации нет; сервис рассчитан на локальный запуск.

## 3. Базовые соглашения

| Тема | Правило |
|---|---|
| Base URL в dev | `/api` через proxy на `http://127.0.0.1:8000` |
| Base URL в prod | тот же origin, `/api` |
| Формат | JSON, UTF-8 |
| Деньги | строки с 2 знаками: `"16242.00"` |
| Цены | строки с 6 знаками: `"302.000000"` |
| Проценты облигаций | строки с 6 знаками: `"95.123000"` |
| Доли | строки с 4 знаками: `"0.2789"` |
| Количества | целые числа |
| Даты | `YYYY-MM-DD` |
| Timestamps | ISO 8601 с таймзоной: `2026-10-30T15:10:12.092327Z` или `2026-10-30T18:10:12+03:00` |
| Пагинация | отсутствует; списки отдают все элементы |
| Формат списков | `{"items": [...]}` там, где это указано ниже |
| Успешные статусы | `201` — создание, `204` — удаление, `200` — остальное |
| Ошибки | единый конверт `{"error": {"code", "message", "details"}}` |
| `X-Request-ID` | возвращается в ответе; можно логировать на клиенте |

**Важно:** не используйте `parseFloat` для денежных расчётов. Строки из API передавайте в форматтеры; `Intl.NumberFormat` принимает `number`, поэтому преобразование строки в число допустимо **только для отображения**, не для арифметики. Клиент не должен пересчитывать суммы, средние, доли и купоны.

## 4. Сводная таблица endpoint'ов

### Служебные

| Метод | Путь | Назначение | Успех |
|---|---|---|---|
| `GET` | `/api/health` | Статус приложения, БД, MOEX, последнее обновление | 200 |

### Портфель

| Метод | Путь | Назначение | Успех |
|---|---|---|---|
| `GET` | `/api/portfolio` | Единственный портфель | 200 |
| `PATCH` | `/api/portfolio` | Переименовать портфель | 200 |

### Активы

| Метод | Путь | Назначение | Успех |
|---|---|---|---|
| `GET` | `/api/assets` | Локальные активы | 200 |
| `GET` | `/api/assets/search?q=` | Поиск в MOEX | 200 |
| `POST` | `/api/assets` | Добавить бумагу из MOEX | 201 |
| `GET` | `/api/assets/{asset_id}` | Карточка актива | 200 |
| `POST` | `/api/assets/{asset_id}/refresh` | Обновить метаданные, купоны, амортизацию | 200 |
| `DELETE` | `/api/assets/{asset_id}` | Удалить, если нет операций и PAID-доходов | 204 |

### Операции

| Метод | Путь | Назначение | Успех |
|---|---|---|---|
| `GET` | `/api/operations?asset_id=&from=&to=` | Список операций | 200 |
| `POST` | `/api/operations` | Создать BUY/SELL | 201 |
| `PATCH` | `/api/operations/{operation_id}` | Изменить операцию | 200 |
| `DELETE` | `/api/operations/{operation_id}` | Удалить операцию | 204 |

### Позиции

| Метод | Путь | Назначение | Успех |
|---|---|---|---|
| `GET` | `/api/positions` | Открытые позиции и итоги | 200 |

### Доходы

| Метод | Путь | Назначение | Успех |
|---|---|---|---|
| `GET` | `/api/income?status=&kind=&asset_id=&from=&to=` | Список доходов и итоги | 200 |
| `POST` | `/api/income` | Ручной фактический дивиденд/купон | 201 |
| `PATCH` | `/api/income/{income_id}` | Изменить доход | 200 |
| `POST` | `/api/income/{income_id}/mark-paid` | Подтвердить ожидаемый купон | 200 |
| `DELETE` | `/api/income/{income_id}` | Удалить доход | 204 |

### Дашборд и snapshots

| Метод | Путь | Назначение | Успех |
|---|---|---|---|
| `GET` | `/api/dashboard?period=1M\|3M\|1Y\|ALL` | Итоги, позиции, график, ближайшие купоны | 200 |
| `GET` | `/api/snapshots?period=1M\|3M\|1Y\|ALL` | Сохранённые дневные snapshots (диагностика) | 200 |

### Котировки

| Метод | Путь | Назначение | Успех |
|---|---|---|---|
| `GET` | `/api/quotes/{asset_id}/history?period=` | История цен актива | 200 |
| `POST` | `/api/quotes/refresh` | Обновить все котировки | 200 |
| `POST` | `/api/quotes/manual` | Добавить ручную цену | 201 |

Периоды истории котировок: `1M`, `3M`, `6M`, `1Y`, `3Y`, `5Y`, `ALL`; по умолчанию `1Y`.

### Настройки

| Метод | Путь | Назначение | Успех |
|---|---|---|---|
| `GET` | `/api/settings` | Эффективные настройки | 200 |
| `PATCH` | `/api/settings` | Изменить разрешённые ключи | 200 |

### Backup и экспорт

| Метод | Путь | Назначение | Успех |
|---|---|---|---|
| `POST` | `/api/backup` | Создать копию SQLite | 200 |
| `GET` | `/api/export?format=json` | Экспорт JSON (по умолчанию) | 200 |
| `GET` | `/api/export?format=csv` | ZIP с тремя CSV | 200 |

## 5. Примеры запросов и ответов

Примеры ниже получены на временной SQLite-БД с `seed_demo` (anchor `2026-10-30`). Большие массивы помечены как сокращённые. Для endpoint'ов, которым нужен MOEX, указано, что ответ — документированная форма.

### 5.1. Health

```bash
curl http://127.0.0.1:8000/api/health
```

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "ok",
  "moex": "unknown",
  "last_quote_refresh_at": null
}
```

- `moex`: `ok` — последний refresh успешен или частично успешен, `error` — последний refresh неуспешен, `unknown` — refresh ещё не выполнялся.
- `last_quote_refresh_at` — локальное время с таймзоной или `null`.
- Если БД недоступна: `status="degraded"`, `database="error"`, `moex="unknown"`.

### 5.2. Портфель

```bash
curl http://127.0.0.1:8000/api/portfolio
```

```json
{
  "id": 1,
  "name": "Мой портфель",
  "base_currency": "RUB",
  "created_at": "2026-10-30T15:10:12.092327Z"
}
```

Переименование:

```bash
curl -X PATCH http://127.0.0.1:8000/api/portfolio \
  -H "Content-Type: application/json" \
  -d '{"name":"Тестовый портфель"}'
```

```json
{
  "id": 1,
  "name": "Тестовый портфель",
  "base_currency": "RUB",
  "created_at": "2026-10-30T15:10:12.092327Z"
}
```

`name` обязателен, обрезается по краям, длина 1–100. Пустая строка → `422 VALIDATION_ERROR`.

### 5.3. Активы

#### Список

```bash
curl http://127.0.0.1:8000/api/assets
```

```json
{
  "items": [
    {
      "id": 1,
      "secid": "SBER",
      "isin": "RU0009029540",
      "name": "Сбербанк",
      "short_name": "Сбербанк",
      "type": "STOCK",
      "board": "TQBR",
      "currency": "RUB",
      "lot_size": 10,
      "is_active": true
    },
    {
      "id": 2,
      "secid": "SU26238RMFS4",
      "isin": "RU000A0JX0J2",
      "name": "ОФЗ 26238",
      "short_name": "ОФЗ 26238",
      "type": "BOND",
      "board": "TQCB",
      "currency": "RUB",
      "lot_size": 1,
      "is_active": true
    }
  ]
}
```

#### Карточка облигации

```bash
curl http://127.0.0.1:8000/api/assets/2
```

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
  "current_face_value": "800.00",
  "lot_size": 1,
  "is_active": true,
  "amortizations": [
    {
      "id": 1,
      "amortization_date": "2026-09-30",
      "amount_per_unit": "200.00",
      "source": "MANUAL"
    }
  ]
}
```

Для акции `initial_face_value` и `current_face_value` — `null`, `amortizations` — пустой массив.

#### Поиск в MOEX

Требует сеть. Ответ — документированная форма.

```bash
curl "http://127.0.0.1:8000/api/assets/search?q=SBER"
```

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

`q` — 1–64 символа. Ошибки MOEX: `404 MOEX_NOT_FOUND`, `502 MOEX_UNAVAILABLE`, `502 MOEX_PARSE_ERROR`.

#### Добавление

Требует сеть. Тело:

```bash
curl -X POST http://127.0.0.1:8000/api/assets \
  -H "Content-Type: application/json" \
  -d '{"secid":"SBER","board":"TQBR"}'
```

Ответ `201` — та же схема, что у `GET /api/assets/{asset_id}`:

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
  "current_face_value": null,
  "lot_size": 10,
  "is_active": true,
  "amortizations": []
}
```

- Поддерживаются только `TQBR` (акции) и `TQCB` (облигации).
- `secid` нормализуется в верхний регистр; `board` должен быть точным (`TQBR`/`TQCB`).
- Повторное добавление → `409 ASSET_ALREADY_EXISTS` (проверяется до обращения к MOEX).
- Неподдерживаемая площадка → `400 BAD_REQUEST` с `details.supported`.
- Для облигации backend сам загружает купоны, амортизацию и историю.

Реальный пример дубликата:

```json
{
  "error": {
    "code": "ASSET_ALREADY_EXISTS",
    "message": "Бумага SBER на площадке TQBR уже добавлена",
    "details": {"secid": "SBER", "board": "TQBR"}
  }
}
```

#### Refresh и удаление

```bash
curl -X POST http://127.0.0.1:8000/api/assets/2/refresh
curl -X DELETE http://127.0.0.1:8000/api/assets/1
```

- `POST /refresh` требует MOEX, возвращает `AssetDetail`; при сбое — `502`.
- `DELETE` возвращает `204` без тела.
- Удаление запрещено, если есть операции или **PAID**-доходы → `409 ASSET_IN_USE`. Ожидаемые купоны удаляются вместе с активом и не блокируют удаление.

```json
{
  "error": {
    "code": "ASSET_IN_USE",
    "message": "Нельзя удалить актив, по которому есть операции или выплаченные доходы",
    "details": {"asset_id": 1}
  }
}
```

### 5.4. Операции

#### Список

```bash
curl "http://127.0.0.1:8000/api/operations?asset_id=1"
```

```json
{
  "items": [
    {
      "id": 1,
      "asset_id": 1,
      "type": "BUY",
      "trade_date": "2026-05-03",
      "quantity": 10,
      "input_price": "100.000000",
      "input_price_type": "RUB",
      "price_rub": "100.000000",
      "note": "Демо-данные"
    },
    {
      "id": 2,
      "asset_id": 1,
      "type": "BUY",
      "trade_date": "2026-07-02",
      "quantity": 10,
      "input_price": "120.000000",
      "input_price_type": "RUB",
      "price_rub": "120.000000",
      "note": "Демо-данные"
    },
    {
      "id": 3,
      "asset_id": 1,
      "type": "SELL",
      "trade_date": "2026-08-31",
      "quantity": 5,
      "input_price": "150.000000",
      "input_price_type": "RUB",
      "price_rub": "150.000000",
      "note": "Демо-данные"
    }
  ]
}
```

`from`/`to` фильтруют по `trade_date` включительно. Сортировка — по `trade_date`, затем `id`.

#### Создание акции

```bash
curl -X POST http://127.0.0.1:8000/api/operations \
  -H "Content-Type: application/json" \
  -d '{"asset_id":1,"type":"BUY","trade_date":"2026-10-29","quantity":5,"price":"300.00","price_type":"RUB","note":"Тестовая покупка"}'
```

```json
{
  "id": 5,
  "asset_id": 1,
  "type": "BUY",
  "trade_date": "2026-10-29",
  "quantity": 5,
  "input_price": "300.000000",
  "input_price_type": "RUB",
  "price_rub": "300.000000",
  "note": "Тестовая покупка"
}
```

#### Создание облигации в процентах

```bash
curl -X POST http://127.0.0.1:8000/api/operations \
  -H "Content-Type: application/json" \
  -d '{"asset_id":2,"type":"BUY","trade_date":"2026-10-29","quantity":1,"price":"97.600","price_type":"PERCENT","note":"Докупка ОФЗ"}'
```

```json
{
  "id": 5,
  "asset_id": 2,
  "type": "BUY",
  "trade_date": "2026-10-29",
  "quantity": 1,
  "input_price": "97.600000",
  "input_price_type": "PERCENT",
  "price_rub": "780.800000",
  "note": "Докупка ОФЗ"
}
```

- Для акций допустим только `price_type="RUB"`; иначе `400 BAD_REQUEST`.
- Для облигаций допустимы `RUB` и `PERCENT`.
- `price_rub` — нормализованная цена, её считает backend.
- `quantity` — целое > 0; `price` > 0, до 6 знаков.
- Будущая `trade_date` разрешена backend, но UI может предупреждать; текущие позиции/итоги учитывают только операции с `trade_date <= today`.

#### Изменение и удаление

```bash
curl -X PATCH http://127.0.0.1:8000/api/operations/5 \
  -H "Content-Type: application/json" \
  -d '{"quantity":6,"note":"Изменено"}'
```

```json
{
  "id": 5,
  "asset_id": 1,
  "type": "BUY",
  "trade_date": "2026-10-29",
  "quantity": 6,
  "input_price": "300.000000",
  "input_price_type": "RUB",
  "price_rub": "300.000000",
  "note": "Изменено"
}
```

```bash
curl -X DELETE http://127.0.0.1:8000/api/operations/5
# 204, тела нет
```

- `PATCH` частичный, но пустое тело или `null` для обязательного поля → `422`.
- Создание/изменение/удаление пересчитывают всю историю актива.
- Продажа больше остатка → `409 INSUFFICIENT_QUANTITY`:

```json
{
  "error": {
    "code": "INSUFFICIENT_QUANTITY",
    "message": "Нельзя продать 20: доступно 15",
    "details": {
      "asset_id": 1,
      "available": 15,
      "requested": 20,
      "operation_id": 5,
      "trade_date": "2026-10-30"
    }
  }
}
```

- Удаление операции, после которого ломается последующая продажа, тоже даёт `409 INSUFFICIENT_QUANTITY`.
- Несуществующая операция → `404 NOT_FOUND`.

### 5.5. Позиции

```bash
curl http://127.0.0.1:8000/api/positions
```

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/positions | ConvertTo-Json -Depth 6
```

```json
{
  "items": [
    {
      "asset": {"id": 1, "secid": "SBER", "name": "Сбербанк", "type": "STOCK"},
      "quantity": 15,
      "avg_price": "110.000000",
      "avg_price_percent": null,
      "current_price": "302.000000",
      "current_price_type": "RUB",
      "current_face_value": null,
      "market_value": "4530.00",
      "invested": "1650.00",
      "share": "0.2789",
      "price_date": "2026-10-30",
      "price_source": "MANUAL",
      "is_stale": false
    },
    {
      "asset": {"id": 2, "secid": "SU26238RMFS4", "name": "ОФЗ 26238", "type": "BOND"},
      "quantity": 15,
      "avg_price": "951.230000",
      "avg_price_percent": "95.123000",
      "current_price": "97.600000",
      "current_price_type": "PERCENT",
      "current_face_value": "800.00",
      "market_value": "11712.00",
      "invested": "14268.45",
      "share": "0.7211",
      "price_date": "2026-10-30",
      "price_source": "MANUAL",
      "is_stale": false
    }
  ],
  "total_market_value": "16242.00",
  "total_invested": "15918.45"
}
```

- Возвращаются только открытые позиции (`quantity > 0`). Актив без операций в `/api/positions` отсутствует; карточка актива должна показывать «нет позиции».
- `price_source`: `MOEX`, `MANUAL` или `COST`.
- `is_stale=true`, если цена не за сегодня (`price_date < today`) или использована себестоимость (`price_source="COST"`).
- `share` — доля позиции в текущей стоимости портфеля.

### 5.6. Доходы

#### Выплаченные

```bash
curl "http://127.0.0.1:8000/api/income?status=PAID"
```

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
      "record_date": "2026-08-21",
      "pay_date": "2026-09-15",
      "source": "MANUAL",
      "note": "Демо-дивиденд",
      "is_overdue": false
    },
    {
      "id": 2,
      "asset_id": 2,
      "asset_secid": "SU26238RMFS4",
      "kind": "COUPON",
      "status": "PAID",
      "amount_per_unit": "35.00",
      "quantity": 15,
      "amount_total": "525.00",
      "currency": "RUB",
      "record_date": null,
      "pay_date": "2026-09-20",
      "source": "MANUAL",
      "note": "Демо-купон",
      "is_overdue": false
    }
  ],
  "totals": {
    "dividends_paid": "200.00",
    "coupons_paid": "525.00",
    "expected_coupons": "1575.00"
  }
}
```

#### Ожидаемые

```bash
curl "http://127.0.0.1:8000/api/income?status=EXPECTED"
```

Сокращённо (фактически три записи):

```json
{
  "items": [
    {
      "id": 3,
      "asset_id": 2,
      "asset_secid": "SU26238RMFS4",
      "kind": "COUPON",
      "status": "EXPECTED",
      "amount_per_unit": "35.00",
      "quantity": 15,
      "amount_total": "525.00",
      "currency": "RUB",
      "record_date": null,
      "pay_date": "2026-11-09",
      "source": "MANUAL",
      "note": null,
      "is_overdue": false
    }
  ],
  "totals": {
    "dividends_paid": "200.00",
    "coupons_paid": "525.00",
    "expected_coupons": "1575.00"
  }
}
```

- `totals` всегда по всему портфелю, даже если применены фильтры. Это нужно явно подписывать в UI.
- Сортировка — по `pay_date`, затем `id`.
- `expected_coupons` включает просроченные ожидаемые купоны; `upcoming_coupons` в дашборде — только будущие.
- `is_overdue=true`, если `pay_date < today` у `EXPECTED`.
- Сумма и количество у `EXPECTED` вычисляются по текущей позиции; у `PAID` берутся сохранённые значения.

#### Ручной доход

```bash
curl -X POST http://127.0.0.1:8000/api/income \
  -H "Content-Type: application/json" \
  -d '{"asset_id":1,"kind":"DIVIDEND","amount_total":"150.00","pay_date":"2026-10-27","quantity":15,"amount_per_unit":"10.00","note":"Ручной дивиденд"}'
```

```json
{
  "id": 6,
  "asset_id": 1,
  "asset_secid": "SBER",
  "kind": "DIVIDEND",
  "status": "PAID",
  "amount_per_unit": "10.00",
  "quantity": 15,
  "amount_total": "150.00",
  "currency": "RUB",
  "record_date": null,
  "pay_date": "2026-10-27",
  "source": "MANUAL",
  "note": "Ручной дивиденд",
  "is_overdue": false
}
```

- `POST /api/income` всегда создаёт `PAID`/`MANUAL`.
- `amount_total` обязательна и > 0. `quantity` опциональна; если не передана — текущее количество.
- `amount_per_unit` опционален; итог авторитетен, цена за единицу выводится из итога.

#### Изменение

```bash
curl -X PATCH http://127.0.0.1:8000/api/income/6 \
  -H "Content-Type: application/json" \
  -d '{"amount_total":"165.00","note":"Уточнено"}'
```

```json
{
  "id": 6,
  "asset_id": 1,
  "asset_secid": "SBER",
  "kind": "DIVIDEND",
  "status": "PAID",
  "amount_per_unit": "11.00",
  "quantity": 15,
  "amount_total": "165.00",
  "currency": "RUB",
  "record_date": null,
  "pay_date": "2026-10-27",
  "source": "MANUAL",
  "note": "Уточнено",
  "is_overdue": false
}
```

- Для `PAID` можно менять `amount_total`, `amount_per_unit`, `quantity`, `record_date`, `pay_date`, `note`.
- Для `EXPECTED` разрешены только `amount_per_unit` (для `MANUAL`), `record_date`, `note`. Сумма, количество и дата выплаты рассчитываются/задаются расписанием; попытка изменить их → `400 BAD_REQUEST`.
- Пустое тело → `422`.

#### Подтверждение купона

```bash
curl -X POST http://127.0.0.1:8000/api/income/3/mark-paid \
  -H "Content-Type: application/json" \
  -d '{"amount_total":"525.00"}'
```

```json
{
  "id": 3,
  "asset_id": 2,
  "asset_secid": "SU26238RMFS4",
  "kind": "COUPON",
  "status": "PAID",
  "amount_per_unit": "35.00",
  "quantity": 15,
  "amount_total": "525.00",
  "currency": "RUB",
  "record_date": null,
  "pay_date": "2026-11-09",
  "source": "MANUAL",
  "note": null,
  "is_overdue": false
}
```

- Тело можно передать пустым `{}`: сумма считается по текущей позиции, дата остаётся прежней.
- Повторное подтверждение → `409 INCOME_ALREADY_PAID`.
- Несуществующий доход → `404 NOT_FOUND`.

```json
{
  "error": {
    "code": "INCOME_ALREADY_PAID",
    "message": "Доход 3 уже выплачен",
    "details": {"income_id": 3}
  }
}
```

#### Удаление

```bash
curl -X DELETE http://127.0.0.1:8000/api/income/6
# 204, тела нет
```

### 5.7. Дашборд

```bash
curl "http://127.0.0.1:8000/api/dashboard?period=1Y"
```

Сокращённо: массив `series` содержит 181 дневную точку, `positions` и `upcoming_coupons` сокращены.

```json
{
  "as_of": "2026-10-30",
  "currency": "RUB",
  "period": "1Y",
  "totals": {
    "market_value": "16242.00",
    "invested": "15918.45",
    "dividends_paid": "200.00",
    "coupons_paid": "525.00",
    "income_paid_total": "725.00",
    "expected_coupons": "1575.00",
    "positions_count": 2,
    "assets_count": 2
  },
  "series": [
    {"date": "2026-05-03", "market_value": "2500.00", "invested": "1000.00", "is_partial": false},
    {"date": "2026-05-04", "market_value": "2500.00", "invested": "1000.00", "is_partial": false}
  ],
  "positions": [
    {
      "asset": {"id": 1, "secid": "SBER", "name": "Сбербанк", "type": "STOCK"},
      "quantity": 15,
      "avg_price": "110.000000",
      "avg_price_percent": null,
      "current_price": "302.000000",
      "current_price_type": "RUB",
      "current_face_value": null,
      "market_value": "4530.00",
      "invested": "1650.00",
      "share": "0.2789",
      "price_date": "2026-10-30",
      "price_source": "MANUAL",
      "is_stale": false
    }
  ],
  "upcoming_coupons": [
    {
      "id": 3,
      "asset_id": 2,
      "asset_secid": "SU26238RMFS4",
      "kind": "COUPON",
      "status": "EXPECTED",
      "amount_per_unit": "35.00",
      "quantity": 15,
      "amount_total": "525.00",
      "currency": "RUB",
      "record_date": null,
      "pay_date": "2026-11-09",
      "source": "MANUAL",
      "note": null,
      "is_overdue": false
    }
  ],
  "is_partial": false
}
```

- `period` опционален. Без него используется сохранённый `dashboard_period` (по умолчанию `1Y`). Явный query-параметр важнее настройки.
- Допустимые периоды: `1M`, `3M`, `1Y`, `ALL`; иначе `422`.
- `series` начинается с `max(начало периода, дата первой операции)`.
- `is_partial=true` на точке — цена взята из себестоимости; верхнеуровневый `is_partial=true`, если хотя бы одна точка частичная.
- `upcoming_coupons` — только `EXPECTED` с `pay_date >= today` и текущим количеством > 0.
- `totals.assets_count` — все активы, включая закрытые позиции; `positions_count` — только открытые.
- `totals` — всевременные выплаты, а `series` — только выбранный период.

### 5.8. Snapshots

```bash
curl "http://127.0.0.1:8000/api/snapshots?period=1M"
```

```json
{
  "period": "1M",
  "items": [
    {
      "date": "2026-10-30",
      "market_value": "16242.00",
      "invested": "15918.45",
      "income_paid": "725.00"
    }
  ]
}
```

- Это сохранённые дневные snapshots, а не источник графика дашборда.
- В demo-seed только один snapshot на дату anchor; поэтому список короткий.
- Периоды те же: `1M`, `3M`, `1Y`, `ALL`; иначе `422`.

### 5.9. История котировок

```bash
curl "http://127.0.0.1:8000/api/quotes/1/history?period=1M"
```

```json
{
  "asset_id": 1,
  "period": "1M",
  "items": [
    {
      "id": 45,
      "asset_id": 1,
      "quote_date": "2026-10-04",
      "price": "294.000000",
      "price_type": "RUB",
      "source": "MANUAL",
      "fetched_at": "2026-10-30T15:10:12.106848Z"
    },
    {
      "id": 53,
      "asset_id": 1,
      "quote_date": "2026-10-30",
      "price": "302.000000",
      "price_type": "RUB",
      "source": "MANUAL",
      "fetched_at": "2026-10-30T15:10:12.106848Z"
    }
  ]
}
```

- Периоды: `1M`, `3M`, `6M`, `1Y`, `3Y`, `5Y`, `ALL`; по умолчанию `1Y`.
- `price_type` для акций — `RUB`, для облигаций — `PERCENT`.
- `source` — `MOEX` или `MANUAL`.
- Ответ отсортирован по дате возрастанию.

### 5.10. Ручная котировка

```bash
curl -X POST http://127.0.0.1:8000/api/quotes/manual \
  -H "Content-Type: application/json" \
  -d '{"asset_id":1,"quote_date":"2026-10-28","price":"305.50","price_type":"RUB"}'
```

```json
{
  "id": 55,
  "asset_id": 1,
  "quote_date": "2026-10-28",
  "price": "305.500000",
  "price_type": "RUB",
  "source": "MANUAL",
  "fetched_at": "2026-10-30T15:10:13.016109Z"
}
```

- `quote_date` не может быть в будущем → `400 BAD_REQUEST`.
- Для акций только `RUB`, для облигаций только `PERCENT`; иначе `400 BAD_REQUEST`.
- Ручная цена перекрывает цену за ту же дату; MOEX не перезаписывает `MANUAL`.
- Ответ `201` даже при обновлении существующей даты.

### 5.11. Обновление котировок

Требует MOEX и может быть медленным. Ответ — документированная форма.

```bash
curl -X POST http://127.0.0.1:8000/api/quotes/refresh
```

```json
{
  "updated": 2,
  "failed": 0,
  "last_refresh_at": "2026-10-30T19:05:00+03:00",
  "errors": []
}
```

При частичном сбое:

```json
{
  "updated": 1,
  "failed": 1,
  "last_refresh_at": "2026-10-30T19:05:00+03:00",
  "errors": [
    {"asset_id": 1, "secid": "SBER", "error": "MOEX недоступен"}
  ]
}
```

- `updated` — число обработанных активов, не число записанных цен.
- `last_refresh_at` — локальное время с таймзоной.
- Ошибка одного актива не ломает остальные; подробности — в `errors[]`.
- Параллельный refresh → `409 REFRESH_IN_PROGRESS` (не `400`).
- Ручной refresh не зависит от настроек `quote_refresh_enabled` и env-master-switch.

### 5.12. Настройки

```bash
curl http://127.0.0.1:8000/api/settings
```

```json
{
  "quote_refresh_enabled": false,
  "dashboard_period": "1Y"
}
```

В этом прогоне `QUOTE_REFRESH_ENABLED=false`, поэтому значение `false`. При стандартном `.env.example` (`true`) и сохранённой настройке по умолчанию будет `true`.

```bash
curl -X PATCH http://127.0.0.1:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{"dashboard_period":"3M"}'
```

```json
{
  "quote_refresh_enabled": false,
  "dashboard_period": "3M"
}
```

- Разрешённые ключи: `quote_refresh_enabled`, `dashboard_period`.
- `PATCH` частичный; возвращает полный набор эффективных значений.
- Пустое тело, `null`, неизвестный ключ или невалидный период → `422 VALIDATION_ERROR`.
- `PATCH quote_refresh_enabled=true` при `QUOTE_REFRESH_ENABLED=false` → `400 BAD_REQUEST`:

```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "Автоматическое обновление котировок отключено настройками развёртывания",
    "details": {}
  }
}
```

### 5.13. Backup

```bash
curl -X POST http://127.0.0.1:8000/api/backup
```

```json
{
  "path": "data/backups/investments-20261030-181012.db",
  "size_bytes": 106496,
  "created_at": "2026-10-30T18:10:12.870080+03:00"
}
```

- `POST /api/backup` возвращает `200`, не `201`.
- Путь повторяет `BACKUP_DIR`: при относительном значении по умолчанию — `data/backups/...`; при абсолютном `BACKUP_DIR` в ответе будет абсолютный POSIX-путь. В temp-прогоне путь был абсолютным.
- Backup-файл **не отдаётся по HTTP**; доступен только путь.
- Ошибки: `400 BAD_REQUEST` для отсутствующей/пустой/немигрированной/не-SQLite БД, `500 INTERNAL_ERROR` для сбоя копирования.

### 5.14. Экспорт

#### JSON

```bash
curl -OJ "http://127.0.0.1:8000/api/export?format=json"
```

Заголовки:

```text
Content-Type: application/json
Content-Disposition: attachment; filename="investments-export-20261030-181012.json"
```

Сокращённый ответ:

```json
{
  "exported_at": "2026-10-30T18:10:12.123456+03:00",
  "app_version": "0.1.0",
  "portfolio": {
    "id": 1,
    "name": "Мой портфель",
    "base_currency": "RUB",
    "created_at": "2026-10-30T15:10:12.092327Z"
  },
  "assets": ["... 2 элемента ..."],
  "operations": [
    {
      "id": 1,
      "asset_id": 1,
      "type": "BUY",
      "trade_date": "2026-05-03",
      "quantity": 10,
      "input_price": "100.000000",
      "input_price_type": "RUB",
      "price_rub": "100.000000",
      "note": "Демо-данные"
    }
  ],
  "income": ["... 5 элементов ..."],
  "quotes": ["... 54 элемента ..."],
  "amortizations": ["... 1 элемент ..."],
  "snapshots": ["... 1 элемент ..."],
  "settings": {
    "demo_seed_anchor": "2026-10-30",
    "demo_seed_version": "1"
  }
}
```

Это человекочитаемая проекция, **не** lossless-формат восстановления. Каноническая копия — SQLite из `POST /api/backup`. Строки-плейсхолдеры `"... N элементов ..."` заменяют массивы объектов; полные схемы элементов — в ответах соответствующих endpoint'ов. `exported_at` зависит от времени запуска.

#### CSV

```bash
curl -OJ "http://127.0.0.1:8000/api/export?format=csv"
```

```text
Content-Type: application/zip
Content-Disposition: attachment; filename="investments-export-20261030-181012.zip"
```

В ZIP ровно три файла:

```text
positions.csv
operations.csv
income.csv
```

CSV — UTF-8 с BOM, CRLF. Значения, начинающиеся с `=`, `+`, `-`, `@`, табуляции или CR, экранируются как текст. Первая строка `positions.csv`:

```text
asset_id,secid,name,type,quantity,avg_price,avg_price_percent,current_price,current_price_type,current_face_value,market_value,invested,share,price_date,price_source,is_stale
```

Невалидный `format` → `422 VALIDATION_ERROR`.

## 6. Ошибки

Единый конверт:

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

| HTTP | Код | Когда |
|---|---|---|
| 400 | `BAD_REQUEST` | Бизнес-валидация: неподдерживаемая площадка, неверный `price_type`, будущая котировка, master-switch, неизменяемое поле EXPECTED |
| 404 | `NOT_FOUND` | Операция/доход не найдены |
| 404 | `ASSET_NOT_FOUND` | Актив не найден |
| 404 | `MOEX_NOT_FOUND` | MOEX не знает бумагу |
| 409 | `ASSET_ALREADY_EXISTS` | Дубликат актива |
| 409 | `ASSET_IN_USE` | Удаление актива с операциями/PAID-доходами |
| 409 | `INSUFFICIENT_QUANTITY` | Продажа больше остатка или удаление ломает историю |
| 409 | `INCOME_ALREADY_PAID` | Повторное подтверждение купона |
| 409 | `REFRESH_IN_PROGRESS` | Параллельный refresh котировок |
| 422 | `VALIDATION_ERROR` | Ошибка Pydantic/query/body |
| 502 | `MOEX_UNAVAILABLE` | MOEX недоступен |
| 502 | `MOEX_PARSE_ERROR` | Неожиданный ответ MOEX |
| 500 | `INTERNAL_ERROR` | Непредвиденная ошибка |

Формат `details.errors` для `422`:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Ошибка валидации данных",
    "details": {
      "errors": [
        {
          "field": "body.quantity",
          "message": "Input should be greater than 0",
          "type": "greater_than"
        }
      ]
    }
  }
}
```

Пример 404:

```json
{
  "error": {
    "code": "ASSET_NOT_FOUND",
    "message": "Актив 9999 не найден",
    "details": {"asset_id": 9999}
  }
}
```

Пример 422 для периода:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Ошибка валидации данных",
    "details": {
      "errors": [
        {
          "field": "query.period",
          "message": "Input should be '1M', '3M', '1Y' or 'ALL'",
          "type": "literal_error"
        }
      ]
    }
  }
}
```

Особый случай: `405 Method Not Allowed` отдаётся с кодом `BAD_REQUEST` и сообщением «Метод не поддерживается». Это нештатный сценарий; в UI не полагайтесь на код для 405.

## 7. Интеграционные заметки для frontend

### 7.1. Деньги и форматирование

- Деньги и цены — строки. Не приводите их к `number` для расчётов.
- Для отображения:

```ts
const rub = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

rub.format(Number('16242.00')); // "16 242,00 ₽"
```

- Для процентов:

```ts
const percent = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 3,
});

`${percent.format(Number('95.123000'))} %`; // "95,123 %"
```

- Для сортировки допустимо вычислить UI-ключ через `Number(...)`, но не использовать его для арифметики.
- Суммы, средние, доли, купоны и итоги всегда берите из API.

### 7.2. Облигации: проценты и `price_type`

- Для облигаций `current_price_type="PERCENT"`, цена — процент от номинала.
- `current_face_value` — текущий номинал после амортизации (в demo — `800.00`).
- `avg_price` — средняя в RUB; `avg_price_percent` — средняя в процентах от взвешенного номинала покупок.
- В операциях `input_price` — то, что ввёл пользователь; `price_rub` — нормализованная цена.
- В форме облигации показывайте переключатель «% от номинала / RUB» и подпись текущего номинала. Не считайте RUB-эквивалент на клиенте; после сохранения покажите `price_rub` из ответа.

### 7.3. `is_stale` и `price_source`

| Значение | UI |
|---|---|
| `price_source="MOEX"`, `is_stale=false` | Обычная цена MOEX |
| `price_source="MANUAL"`, `is_stale=false` | Ручная цена за сегодня; можно показать бейдж «вручную» |
| `is_stale=true` | Цена не за сегодня; показать `price_date` и предупреждение «цена от …» |
| `price_source="COST"` | Котировок нет; стоимость равна себестоимости; сильное предупреждение |

`is_stale` не означает «битые данные»: это признак, что последняя цена старше сегодняшней даты.

### 7.4. `is_partial` на графике

- `dashboard.is_partial=true` — хотя бы одна точка ряда оценена по себестоимости.
- `series[].is_partial=true` — конкретная точка.
- Показывайте предупреждение над графиком: «Часть графика оценена по себестоимости: по некоторым активам нет исторических котировок».
- Не скрывайте такие точки и не интерполируйте их на клиенте.

### 7.5. Ошибки, которые важны в UX

| Код | Действие |
|---|---|
| `409 INSUFFICIENT_QUANTITY` | Показать `details.available` и `details.requested`; не отправлять повторно без изменения количества |
| `409 ASSET_IN_USE` | Объяснить, что есть операции или выплаченные доходы; предложить оставить актив |
| `409 INCOME_ALREADY_PAID` | Обновить список доходов; показать, что купон уже выплачен |
| `409 REFRESH_IN_PROGRESS` | Показать «Обновление уже выполняется», не запускать повторный запрос сразу |
| `400 BAD_REQUEST` | Показать `message`; для настроек — объяснить master-switch |
| `422 VALIDATION_ERROR` | Подсветить поля по `details.errors[].field` |
| `502 MOEX_*` | Предложить повторить позже; данные из кэша остаются доступны |
| `404 ASSET_NOT_FOUND` | Вернуть пользователя в портфель |

### 7.6. Скачивание файлов

`Content-Disposition` доступен из CORS. Скачивайте через blob:

```ts
this.http.get('/api/export', {
  params: { format: 'csv' },
  observe: 'response',
  responseType: 'blob',
}).subscribe((response) => {
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  const filename = match?.[1] ?? 'investments-export.zip';
  const url = URL.createObjectURL(response.body!);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
});
```

- JSON: `investments-export-YYYYMMDD-HHMMSS.json`.
- CSV: `investments-export-YYYYMMDD-HHMMSS.zip`.
- Backup-файл по HTTP не скачивается; показывайте только `path`.

### 7.7. Master-switch настроек

- `GET /api/settings` возвращает **эффективное** значение `quote_refresh_enabled = env AND stored`.
- Если env `false`, GET всегда `false`, а `PATCH true` → `400`.
- Если env `true`, сохранённая настройка управляет плановыми запусками.
- UI не может отличить env `false` от сохранённого `false` по GET. Поэтому:
  - показывайте переключатель;
  - при `400` возвращайте его в прежнее состояние и объясняйте, что автоматическое обновление отключено настройками развёртывания;
  - ручной `POST /api/quotes/refresh` доступен всегда.

### 7.8. Обновление котировок

- Может занимать секунды/десятки секунд: показывайте loading, блокируйте кнопку, не запускайте параллельно.
- Обрабатывайте `409 REFRESH_IN_PROGRESS`.
- После успеха обновите `/api/health`, `/api/dashboard`, `/api/positions`.
- `errors[]` может быть непустым при `200`; покажите предупреждение, а не общий успех.

### 7.9. Даты и время

- `trade_date`, `pay_date`, `quote_date`, `date`, `as_of` — даты без времени; не применяйте таймзону.
- `created_at`, `fetched_at` — UTC ISO; `last_quote_refresh_at`, `backup.created_at` — локальное время с `+03:00`.
- Для дат используйте `DatePipe` с `ru-RU`; для timestamps — с таймзоной или `Intl.DateTimeFormat`.

## 8. OpenAPI и генерация типов

```bash
# 1. Запустить backend
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2. Сгенерировать TypeScript-типы
npx openapi-typescript http://127.0.0.1:8000/openapi.json -o src/app/core/api/schema.ts
```

Альтернатива — Angular-клиент:

```bash
npx @openapitools/openapi-generator-cli generate \
  -i http://127.0.0.1:8000/openapi.json \
  -g typescript-angular \
  -o src/app/core/api/generated
```

Рекомендуется `openapi-typescript`: он даёт типы без навязанного клиента, а тонкий `ApiClient` пишется вручную. Сгенерированный файл не редактировать вручную; при изменении backend перегенерировать и проверить diff.

## 9. Данные для приёмки frontend (demo seed)

Значения получены из временной seeded-БД; anchor — `2026-10-30`. При запуске seed в другую дату относительные даты сдвинутся, суммы останутся теми же.

### Портфель и активы

| Показатель | Значение |
|---|---|
| Портфель | «Мой портфель», RUB |
| SBER | 15 шт., средняя `110.000000` RUB |
| SBER текущая цена | `302.000000` RUB |
| SBER стоимость / вложено | `4530.00` / `1650.00` |
| SBER доля | `0.2789` |
| ОФЗ 26238 | 15 шт., средняя `951.230000` RUB, `95.123000 %` |
| ОФЗ текущая цена | `97.600000 %` |
| ОФЗ номинал | initial `1000.00`, current `800.00` (амортизация `200.00` от `2026-09-30`) |
| ОФЗ стоимость / вложено | `11712.00` / `14268.45` |
| ОФЗ доля | `0.7211` |
| Итого стоимость / вложено | `16242.00` / `15918.45` |

### Дашборд

| Показатель | Значение |
|---|---|
| `market_value` | `16242.00` |
| `invested` | `15918.45` |
| `dividends_paid` | `200.00` |
| `coupons_paid` | `525.00` |
| `income_paid_total` | `725.00` |
| `expected_coupons` | `1575.00` |
| `positions_count` | `2` |
| `assets_count` | `2` |
| `is_partial` | `false` |
| Точек в `1Y` | 181 (с `2026-05-03` по `2026-10-30`) |
| Точек в `1M` | 31 |

### Доходы

| Запись | Значение |
|---|---|
| Дивиденд SBER | `PAID`, `200.00`, 20 шт. × `10.00`, pay_date `2026-09-15` |
| Купон ОФЗ | `PAID`, `525.00`, 15 шт. × `35.00`, pay_date `2026-09-20` |
| Ожидаемые купоны | 3 × `525.00`, pay_date `2026-11-09`, `2027-02-07`, `2027-05-08` |
| Итого ожидаемых | `1575.00` |
| Snapshot на сегодня | `16242.00` / `15918.45` / `725.00` |

### Настройки и здоровье

| Показатель | Значение |
|---|---|
| Health | `status=ok`, `version=0.1.0`, `database=ok`, `moex=unknown`, `last_quote_refresh_at=null` |
| `dashboard_period` | `1Y` |
| `quote_refresh_enabled` | в temp-прогоне `false` (env `QUOTE_REFRESH_ENABLED=false`); при стандартном env `true` — `true` |

## 10. Расхождения с PLAN.md (справочно)

`PLAN.md` §8 — черновик; фактический контракт шире. `PLAN.md` не изменялся.

| Что в `PLAN.md` | Фактически |
|---|---|
| Нет `GET /api/assets` (списка) | Есть; используется для портфеля |
| `POST /api/assets` без описания тела | Тело: `{"secid": "...", "board": "TQBR\|TQCB"}` |
| Нет `PATCH /api/portfolio` | Есть; переименование портфеля |
| Нет `POST /api/assets/{id}/refresh` | Есть; обновление метаданных/расписаний |
| Нет `POST /api/quotes/manual` | Есть; ручная цена |
| Нет `GET/PATCH /api/settings` | Есть; эффективные настройки |
| Нет `GET /api/snapshots` | Есть; диагностические snapshots |
| `DELETE /api/assets/{id}` — «только если нет операций» | Дополнительно блокируется при наличии PAID-доходов |
| `GET /api/income?status=&kind=` | Дополнительно `asset_id`, `from`, `to` |
| `GET /api/quotes/{asset_id}/history?period=` без списка периодов | `1M/3M/6M/1Y/3Y/5Y/ALL` |
| `/api/openapi.json` (в `BACKEND_PLAN` §8.1) | Только `/openapi.json` |
| В таблице ошибок `BACKEND_PLAN` §8.11 нет `REFRESH_IN_PROGRESS` и `MOEX_NOT_FOUND` | Фактические коды: `409 REFRESH_IN_PROGRESS`, `404 MOEX_NOT_FOUND` |
| Пример `expected_coupons` = `525.00` | В seed три ожидаемых купона: `1575.00` |
| Пример пути backup всегда `data/backups/...` | Зависит от `BACKUP_DIR`: при абсолютном значении путь абсолютный |

## 11. Чек-лист старта frontend

- [ ] Backend поднят на `127.0.0.1:8000`, `/api/health` отвечает `200`.
- [ ] `alembic upgrade head` выполнен, `seed_demo` загружен.
- [ ] `GET /api/positions` отдаёт SBER 15 @110 и ОФЗ 15 @95.123%.
- [ ] OpenAPI скачан с `/openapi.json`, типы сгенерированы.
- [ ] Dev proxy `/api` → `http://127.0.0.1:8000` работает.
- [ ] CORS не нужен в prod (same origin), в dev — origin `localhost:4200`/`127.0.0.1:4200`.
- [ ] Форматтеры денег/процентов/дат написаны, `parseFloat` не используется для расчётов.
- [ ] Обработаны `409 INSUFFICIENT_QUANTITY`, `409 ASSET_IN_USE`, `409 INCOME_ALREADY_PAID`, `409 REFRESH_IN_PROGRESS`.
- [ ] Скачивание JSON/CSV читает `Content-Disposition`.
- [ ] `is_stale`, `price_source`, `is_partial` отображаются по правилам выше.

---

**Связанные документы:** [`PLAN.md`](../PLAN.md), [`BACKEND_PLAN.md`](BACKEND_PLAN.md), [`BACKEND_PROGRESS.md`](BACKEND_PROGRESS.md), [`FRONTEND_PLAN.md`](FRONTEND_PLAN.md).
