# Учет инвестиций — frontend

Angular-приложение для локального учёта одного инвестиционного портфеля. Работает
только с backend API `/api`; все бизнес-расчёты (стоимость, средние, доли,
купоны, итоги) выполняет backend.

## Экраны

Все экраны реализованы, заглушек Stage 0 больше нет:

| Маршрут | Экран |
|---|---|
| `/dashboard` | Итоги портфеля, график стоимости, открытые позиции и ближайшие купоны; переключатель периода `1M/3M/1Y/ALL` |
| `/portfolio` | Позиции, итоги, фильтр «Все/Акции/Облигации», поиск и добавление активов MOEX |
| `/assets/:assetId` | Карточка актива: позиция, операции BUY/SELL (создание, редактирование, удаление), доходы, история котировок |
| `/income` | Доходы: вкладки выплаченных и ожидаемых, фильтры, создание/редактирование/удаление, отметка «выплачен» |
| `/settings` | Настройки обновления котировок и периода дашборда, статус системы, ручной refresh MOEX, backup и экспорт JSON/CSV |

`/` перенаправляет на `/dashboard`; неизвестный маршрут показывает страницу
«Не найдено».

## Стек и версии

| Компонент | Версия |
|---|---|
| Node.js / npm | 24.22.0 / 11.19.1 (подходят LTS 20/22/24) |
| Angular core / CLI / build | **20.3.34** / **20.3.42** / **20.3.42** |
| PrimeNG / `@primeuix/themes` | **20.4.0** / **2.0.0** (MIT, без license key) |
| TypeScript / RxJS / Zone.js | **5.9.3** / **7.8.2** / **0.15.1** |
| Chart.js | **4.4.9** |
| Karma / Jasmine | **6.4.4** / **5.9.0** |
| `openapi-typescript` | **7.13.0** |

PrimeNG 20.x и 21.x — MIT-линейка; PrimeNG 22+ требует коммерческую
лицензию. Не обновляйте PrimeNG до 22+ без юридического решения.

## Установка и dev-запуск

```powershell
cd frontend
npm ci
npm start
```

Приложение: <http://localhost:4200>. Dev-сервер проксирует `/api` на
`http://127.0.0.1:8000` (`proxy.conf.json`). Backend запускается отдельно:

```powershell
cd ..\backend
python -m uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Проверка прокси: <http://localhost:4200/api/health>. Если `uv` не установлен,
используйте `python -m uv ...`; миграции: `uv run alembic upgrade head`.

### Демо-данные

Seed создаёт портфель, SBER, ОФЗ 26238, операции, котировки и доходы без
обращений к сети:

```powershell
cd backend
uv run alembic upgrade head
uv run python -m app.scripts.seed_demo
```

Повторный seed идемпотентен. Подробнее — в
[`backend/README.md`](../backend/README.md).

## Тесты

```powershell
# Edge (Windows)
$env:CHROME_BIN = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
npm run test:ci

# либо Chrome
$env:CHROME_BIN = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
npm run test:ci
```

`test:ci` = `ng test --watch=false --browsers=ChromeHeadless`; `npm test`
запускает watch-режим. Тесты не ходят в реальный HTTP: сервисы мокаются, для
клиента используется `provideHttpClientTesting()`.

## Сборка

```powershell
npm run build
```

Angular 20 application builder пишет production-сборку в
**`<repo-root>\dist\browser`** (в этом репозитории —
`D:\Work\ai test\dist\browser`) благодаря `"outputPath": { "base": "../dist" }`
в `angular.json`. Не путайте с `frontend/dist`: FastAPI раздаёт только
repo-root `dist/browser`.

## Production: FastAPI + `start.ps1`

Одна команда из корня репозитория:

```powershell
.\start.ps1
```

Скрипт проверяет `uv` (fallback — `python -m uv`), выполняет
`alembic upgrade head` в `backend`, при отсутствии `dist/browser/index.html`
проверяет Node/npm, при необходимости делает `npm ci` и `npm run build`, затем
запускает `uvicorn app.main:app --host 127.0.0.1 --port 8000` и открывает
браузер только после успешного `GET /api/health` (poll с таймаутом).

Параметры:

```powershell
.\start.ps1 -Build                 # пересобрать frontend перед запуском
.\start.ps1 -Port 8010             # другой порт
.\start.ps1 -NoBrowser             # не открывать браузер
.\start.ps1 -HealthTimeoutSeconds 120  # ждать health-check до 120 секунд
.\start.ps1 -NpmCi -Build          # принудительный чистый npm ci
```

FastAPI после API-роутов раздаёт `dist/browser`: существующий файл отдаётся
напрямую, неизвестный не-API путь (`/dashboard`, `/assets/1`) — `index.html`.
`/api/*`, `/docs` и `/openapi.json` в SPA-fallback не попадают. `index.html`
отдаётся с `Cache-Control: no-cache`, хэшированные JS/CSS/шрифты/картинки — с
`public, max-age=31536000, immutable`. Если сборки нет, статика не включается и
API/dev-режим продолжают работать.

Ручной эквивалент:

```powershell
cd backend
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Генерация типов API

Backend должен быть запущен:

```powershell
npm run api:types
```

Скрипт: `openapi-typescript http://127.0.0.1:8000/openapi.json -o src/app/core/api/schema.ts`.
`schema.ts` не редактируется вручную; после изменения backend перегенерируйте
файл и проверьте diff. Удобные алиасы — в `src/app/core/api/models.ts`.
`environment.ts` и `environment.development.ts` используют `apiBaseUrl: '/api'`,
поэтому dev-proxy и production работают на одном origin.

## Структура

```text
src/app/
├── app.component.ts          # корень, <router-outlet />
├── app.config.ts             # router, HTTP + interceptor, PrimeNG Aura, ru-RU
├── app.routes.ts             # shell + lazy-страницы
├── core/
│   ├── api/                  # ApiClient, ApiError, schema.ts, models.ts
│   ├── interceptors/         # api-error.interceptor.ts
│   ├── formatting/           # money/price/percent/share/date pipes, validators
│   └── services/             # dashboard, portfolio, positions, assets, operations,
│                             # income, quotes, settings, system, health, notifications
├── layout/
│   ├── shell/                # sticky topbar, router outlet, toast, confirm
│   ├── sidebar/              # desktop navigation
│   └── navigation.ts         # nav model + active-section mapping
├── shared/
│   ├── a11y/                 # focus helpers, aria-describedby
│   ├── forms/                # server field errors
│   └── ui/                   # page-header, stat-card, positions-table, chart,
│                             # period-switcher, empty/error/loading states, badges
└── features/
    ├── dashboard/
    ├── portfolio/            # + asset-search-dialog
    ├── asset-detail/         # + operation-dialog
    ├── income/               # + income-form/mark-paid dialogs
    ├── settings/
    └── not-found/
```

Оболочка: sticky topbar + desktop sidebar (≥ 901 px) и hamburger/slide-down меню
на мобильных (≤ 900 px). Активный раздел подсвечивается, `aria-current="page"`
выставляется из одного `activeSection` signal; `/assets/:assetId` относится к
разделу «Портфель».

## Деньги, цены и даты

- Все денежные значения приходят с API **строками** (`"16242.00"`), цены —
  строки с 6 знаками (`"302.000000"`). Клиент не пересчитывает суммы, средние,
  доли и купоны.
- Преобразование строки в `number` допустимо только для отображения в
  `Intl.NumberFormat` (пайпы `money`, `price`, `percent`, `share`).
- `PercentPipe` — для значений, уже выраженных в процентах (`95.123000`).
  `SharePipe` — только для долей портфеля (`0.2789` → `27,89 %`).
- Даты `YYYY-MM-DD` форматируются без `Date`/таймзоны; ISO timestamps — в
  локальной таймзоне браузера (`date` pipe). Длинные доли секунды
  нормализуются до миллисекунд.

## Ограничения

- Поддерживаются площадки MOEX `TQBR` (акции), `TQCB` (корпоративные
  облигации) и `TQOB` (ОФЗ). ОФЗ на `TQOB` поддерживаются.
- Нет авторизации и мультипортфельности: сервис рассчитан на локальный запуск
  `127.0.0.1` с одним портфелем «Мой портфель».
- Тёмная тема отключена; внешние шрифты не используются, приложение работает
  офлайн (кроме запросов к API/MOEX на backend).
- A11y Stage 5: не проверялись реальные скринридеры, W3C validator,
  Firefox/Safari и инструментальный contrast; Playwright E2E не добавлен.
  Остаётся опциональный `aria-controls` неактивной вкладки `/income`.
- `npm audit --omit=dev`: **0 vulnerabilities**. Полный `npm audit` показывает
  **24 moderate в dev-инструментах** (Angular CLI/build, Karma,
  `openapi-typescript`); high/critical — 0. Это dev-зависимости, production-бандл
  они не затрагивают; обновление требует отдельного решения.

## Диагностика

- **`/api/*` возвращает 404 в dev** — backend не запущен или слушает другой
  порт; проверьте <http://127.0.0.1:8000/api/health>.
- **Production deep link отдаёт JSON 404** — не собран `dist/browser/index.html`
  или FastAPI запущен из другого repo-root; выполните `npm run build` и
  перезапустите `start.ps1`.
- **Порт 8000 занят** — остановите старый процесс либо запустите
  `.\start.ps1 -Port 8010`.
- **Karma не находит браузер** — задайте `CHROME_BIN` (Edge/Chrome) и повторите
  `npm run test:ci`.
- **Устаревшая сборка после изменений** — `.\start.ps1 -Build` или удалите
  `dist`/`.angular/cache`, затем `npm run build`.
- **Нет таблиц / health показывает ошибку БД** — выполните
  `uv run alembic upgrade head` в `backend`.
