# Учет инвестиций — frontend

Angular-приложение для локального учёта инвестиционного портфеля. Работает
только с backend API `/api`; все бизнес-расчёты (стоимость, средние, доли,
купоны, итоги) выполняет backend.

## Стек и точные версии

| Компонент | Версия | Примечание |
|---|---|---|
| Node.js | 24.22.0 | официально поддерживается Angular 20; для CI годятся 20/22/24 LTS |
| npm | 11.19.1 | lockfile — `package-lock.json` |
| Angular core / common / compiler / forms / platform-browser / router | **20.3.34** | standalone-компоненты, signals |
| `@angular/animations` | **20.3.34** | нужен PrimeNG; в Angular 20 помечен deprecated |
| Angular CLI / `@angular/build` | **20.3.42** | builder `@angular/build:application` |
| `@angular/compiler-cli` | **20.3.34** | |
| `@angular/cdk` | **20.2.14** | |
| PrimeNG | **20.4.0** | MIT, license key не требуется |
| `@primeuix/themes` | **2.0.0** | MIT, preset Aura, только светлая тема |
| PrimeIcons | **7.0.0** | |
| Chart.js | **4.4.9** | для `p-chart` на этапе дашборда |
| TypeScript | **5.9.3** | |
| RxJS | **7.8.2** | |
| Zone.js | **0.15.1** | классический change detection |
| Karma / Jasmine | **6.4.4** / **5.9.0** | headless Edge/Chrome |
| `openapi-typescript` | **7.13.0** | генерация `schema.ts` |

### Лицензии и rationale

- PrimeNG **19–21 — MIT**, PrimeNG **22+ — коммерческая лицензия**. Проект
  запинен на **PrimeNG 20.4.0** и **Angular 20.3.34**: это текущая
  поддерживаемая MIT-линейка с security-патчами.
- `@primeuix/themes` 2.0.0 — MIT; license key в `providePrimeNG` не
  передаётся.
- Angular 18 больше не используется: он выведен из поддержки и имеет
  известные advisories. Не обновляйте PrimeNG до 22+ без юридического решения.

## Установка и запуск

```powershell
cd frontend
npm ci
npm start
```

Приложение: <http://localhost:4200>.

Dev-сервер проксирует `/api` на backend `http://127.0.0.1:8000`
(`proxy.conf.json`, `changeOrigin: true`). Backend запускается отдельно:

```powershell
cd ..\backend
python -m uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Проверка прокси: <http://localhost:4200/api/health>.

### Окружения

- `src/environments/environment.ts` — базовое (production) окружение.
- `src/environments/environment.development.ts` — development, подставляется
  через `fileReplacements` в конфигурации `development` (`angular.json`).
- В обоих `apiBaseUrl: '/api'`: dev-proxy и production-раздача используют тот
  же origin.

## Сборка

```powershell
npm run build
```

Angular 20 application builder пишет результат в **`D:\Work\ai test\dist\browser`**
(`"outputPath": { "base": "../dist" }` в `angular.json`). Именно этот путь
ожидает FastAPI при раздаче статики на этапе 6.

## Тесты

```powershell
# Edge (Windows)
$env:CHROME_BIN = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
npm run test:ci
```

`test:ci` = `ng test --watch=false --browsers=ChromeHeadless`. Можно указать
`CHROME_BIN` на Chrome. `npm test` запускает watch-режим.

Тесты не ходят в реальный HTTP: сервисы мокаются, для клиента и smoke-теста
приложения используется `provideHttpClientTesting()`.

## Генерация типов API

Backend должен быть запущен (OpenAPI доступен только по `/openapi.json`):

```powershell
npm run api:types
```

Скрипт: `openapi-typescript http://127.0.0.1:8000/openapi.json -o src/app/core/api/schema.ts`.
`schema.ts` не редактируется вручную; после изменения backend перегенерируйте
файл и проверьте diff. Удобные алиасы — в `src/app/core/api/models.ts`.

## Структура

```text
src/app/
├── app.component.ts          # корень, только <router-outlet />
├── app.config.ts             # router, HTTP + interceptor, PrimeNG Aura, ru-RU
├── app.routes.ts             # shell + lazy-страницы
├── core/
│   ├── api/                  # ApiClient, ApiError, schema.ts, models.ts
│   ├── interceptors/         # api-error.interceptor.ts
│   ├── formatting/           # money / price / percent / share / date pipes
│   └── services/             # health, notifications, loading
├── layout/
│   ├── shell/                # sticky topbar, router outlet, toast, confirm
│   ├── sidebar/              # desktop navigation
│   └── navigation.ts         # nav model + active-section mapping
├── shared/ui/                # page-header, stat-card, empty/error state, ...
└── features/                 # dashboard, portfolio, asset-detail, income,
                              # settings, not-found (пока заглушки)
```

Оболочка: компактный sticky topbar + desktop sidebar (≥ 901 px) и
hamburger/slide-down меню на мобильных (≤ 900 px). Активный раздел
подсвечивается, `aria-current="page"` выставляется из одного `activeSection`
signal; `/assets/:assetId` относится к разделу «Портфель».

## Деньги, цены и даты

- Все денежные значения приходят с API **строками** (`"16242.00"`), цены —
  строки с 6 знаками (`"302.000000"`). Клиент не пересчитывает суммы,
  средние, доли и купоны.
- Преобразование строки в `number` допустимо только для отображения в
  `Intl.NumberFormat` (пайпы `money`, `price`, `percent`, `share`).
- `PercentPipe` — для значений, уже выраженных в процентах (`95.123000`).
  `SharePipe` — только для долей портфеля (`0.2789` → `27,89 %`).
- Даты `YYYY-MM-DD` форматируются без `Date`/таймзоны; ISO timestamps — в
  локальной таймзоне браузера (`date` pipe). Длинные доли секунды
  нормализуются до миллисекунд.

## Ограничения Stage 0

- Дашборд, портфель, карточка актива, доходы и настройки — заглушки с
  `PageHeader`/`EmptyState`; бизнес-данные не запрашиваются.
- Тёмная тема отключена (`darkModeSelector: false`), внешние шрифты не
  используются (приложение работает офлайн).
- `npm ci` / `npm audit` на этой линейке: **0 vulnerabilities** (включая
  0 high/critical).
