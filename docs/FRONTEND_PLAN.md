# План реализации frontend — «Учет инвестиций»

- **Версия:** 1.0
- **Дата:** 2026-10-30
- **Статус:** готов к исполнению
- **Стек:** Angular 20.3.34 (CLI/build 20.3.42) + PrimeNG 20.4.0 (MIT) + `@primeuix/themes` 2.0.0 + Chart.js 4.4.9, TypeScript 5.9.3, SCSS, Karma + Jasmine
- **Связанные документы:** [`PLAN.md`](../PLAN.md), [`BACKEND_PLAN.md`](BACKEND_PLAN.md), [`FRONTEND_HANDOFF.md`](FRONTEND_HANDOFF.md)

## Прогресс

| Этап | Содержание | Статус | Ревью |
|---|---|---|---|
| 0 | Каркас, shell, тема, routing, proxy, API/error/formatting foundation | [x] | [x] |
| 1 | Data layer + Dashboard | [x] | [x] |
| 2 | Portfolio + asset search/add + asset detail + operations CRUD | [ ] | [ ] |
| 3 | Income | [ ] | [ ] |
| 4 | Settings/system | [ ] | [ ] |
| 5 | UX polish, responsive, a11y, ru-RU, E2E | [ ] | [ ] |
| 6 | Production integration, final tests, docs | [ ] | [ ] |

## 1. Цель и границы

### 1.1. Цель

Собрать локальное Angular-приложение, которое закрывает пять экранов MVP:

1. Дашборд.
2. Портфель.
3. Карточка актива.
4. Доходы.
5. Настройки.

Frontend работает только с замороженным API `/api`, не обращается к MOEX и не дублирует бизнес-расчёты backend.

### 1.2. Входит

- [ ] Просмотр итогов, позиций, графика стоимости и ближайших купонов.
- [ ] Поиск бумаг в MOEX через backend и добавление актива.
- [ ] Создание, редактирование и удаление операций BUY/SELL.
- [ ] Карточка актива с позицией, операциями, доходами и историей цен.
- [ ] Выплаченные и ожидаемые доходы, ручное добавление, подтверждение, редактирование, удаление.
- [ ] Настройки: автообновление, период дашборда, refresh, backup, экспорт JSON/CSV, health.
- [ ] Адаптивная светлая тема, русский интерфейс, доступность с клавиатуры.
- [ ] Production-сборка, раздача через FastAPI, `start.ps1`.

### 1.3. Не входит

- Авторизация и многопользовательский режим.
- Несколько портфелей.
- Иностранные активы, валюта, крипта.
- Комиссии, налоги, реализованная прибыль, FIFO, XIRR, TWR.
- Ожидаемые дивиденды и прогнозы.
- Импорт брокерских отчётов.
- Мобильное приложение; только адаптивная вёрстка.
- Playwright E2E в MVP; ручной сценарий обязателен, автоматизация — позже.

## 2. Стек и проверенные решения

Проверено 2026-10-30 на локальной машине: smoke-тест подтвердил `ng build` и Karma/Chrome headless на Angular 20.3.34 + Node 24.22.

| Компонент | Решение | Проверка |
|---|---|---|
| Node.js | 24.x локально (проверено `v24.22.0`); для CI — Node 20/22/24 LTS | Node 24 входит в официальный диапазон Angular 20 |
| npm | 11.x | локально `11.19.1` |
| Angular | 20.3.34, standalone + signals | установлен `@angular/core` 20.3.34 |
| Angular CLI | 20.3.42 | установлен `@angular/cli` 20.3.42 |
| Builder | `@angular/build:application` | сгенерированный `angular.json` |
| Тесты | Karma + Jasmine через `@angular/build:karma`; Chrome/Edge headless | `ng test`; `CHROME_BIN` + `--browsers=ChromeHeadless` |
| TypeScript | 5.9.3 | точный пин в `package.json` |
| RxJS | 7.8.2 | точный пин в `package.json` |
| Zone.js | 0.15.1 | точный пин в `package.json` |
| PrimeNG | **20.4.0** (точный пин, MIT) | MIT-линия 19–21; поддерживает Angular 20 |
| PrimeUI themes | `@primeuix/themes` **2.0.0**, preset Aura | MIT-линия 2.x; 3.x — коммерческая |
| Angular CDK | 20.2.14 | опционально; совместим с Angular 20 |
| Chart.js | 4.4.9 через `p-chart` | `p-chart` в PrimeNG 20 не deprecated |
| Иконки | PrimeIcons 7.0.0 | точный пин; совместим с PrimeNG 20.4.0 |
| Стили | SCSS | scaffold |
| Формы | Reactive Forms | решение |
| Состояние | signals + сервисы, без NgRx | решение |
| Пакеты | npm, `package-lock.json` | scaffold |

> **Node:** Angular 20 официально поддерживает Node 20.19+/22.12+/24.x. Связка Node 24.22 + Angular 20.3.34 проверена локально (`ng build`, Karma/Chrome headless), `npm audit` — 0 vulnerabilities. Версию зафиксировать в `.nvmrc`/README.

### 2.1. Решение по PrimeNG: 20.4.0 (MIT)

PrimeNG **19–21** распространяются по MIT; версии **≥22** — коммерческая лицензия с license key. Проект пинует **PrimeNG 20.4.0** — текущую MIT-линию, которая поддерживает Angular 20 и не тянет security advisories устаревшей линии Angular. Темы: `@primeuix/themes` **2.x — MIT**, **3.x — коммерческая**; используется **2.0.0**.

- Версии пинуются точно, без `^`: `"primeng": "20.4.0"`, `"@primeuix/themes": "2.0.0"`.
- License key не нужен; поле `license` в `providePrimeNG` не передаётся.
- Переход на PrimeNG ≥22 / `@primeuix/themes` 3.x — отдельное решение с юридической проверкой, вне MVP.

```ts
import Aura from '@primeuix/themes/aura';
import { providePrimeNG } from 'primeng/config';

providePrimeNG({
  theme: {
    preset: Aura,
    options: { darkModeSelector: false }, // только светлая тема
  },
  ripple: true,
});
```

### 2.2. Chart в PrimeNG 20

В PrimeNG 20 компонент `p-chart` не deprecated: используем `ChartModule` из `primeng/chart` и Chart.js 4.4.9. При этом:

- оборачиваем его в собственный `ValueChartComponent`;
- не размазываем Chart.js по фичам;
- при будущем обновлении PrimeNG меняем только обёртку.

### 2.3. Тестовый раннер: Karma + Jasmine

Angular 20 CLI использует тестовый builder `@angular/build:karma`; `karma.conf.js` не генерируется. Jasmine и `tsconfig.spec.json` — тестовый раннер проекта; конфигурация живёт в target `test` в `angular.json`.

- `npm test` запускает `ng test` в watch-режиме.
- CI/локально без watch: `npm test -- --watch=false --browsers=ChromeHeadless` (эквивалент скрипта `npm run test:ci`).
- Headless-браузер задаётся через `CHROME_BIN`, например Edge:
  `$env:CHROME_BIN = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"`.
- Отдельный `karma.conf.js` и кастомный launcher не нужны: `ChromeHeadless` + `CHROME_BIN`, указывающий на Edge/Chrome.
- Отдельный CI-скрипт не нужен: эта же команда используется в CI.

## 3. Архитектура

```text
frontend/
├── angular.json
├── package.json
├── proxy.conf.json
├── public/
└── src/
    ├── main.ts
    ├── styles.scss
    └── app/
        ├── app.component.ts
        ├── app.config.ts
        ├── app.routes.ts
        ├── core/
        │   ├── api/
        │   │   ├── api-client.service.ts
        │   │   ├── api-error.ts
        │   │   ├── schema.ts          # generated by openapi-typescript
        │   │   └── models.ts          # aliases + client-only types
        │   ├── interceptors/
        │   │   └── api-error.interceptor.ts
        │   ├── formatting/
        │   │   ├── money.pipe.ts
        │   │   ├── price.pipe.ts
        │   │   ├── percent.pipe.ts
        │   │   ├── share.pipe.ts
        │   │   ├── date.pipe.ts
        │   │   └── number-input.ts
        │   └── services/
        │       ├── health.service.ts
        │       └── notification.service.ts
        ├── shared/
        │   └── ui/
        │       ├── page-header/
        │       ├── stat-card/
        │       ├── empty-state/
        │       ├── error-state/
        │       ├── loading-skeleton/
        │       ├── period-switcher/
        │       └── price-source-badge/
        ├── layout/
        │   ├── navigation.ts
        │   ├── shell/
        │   └── sidebar/
        └── features/
            ├── dashboard/
            ├── portfolio/
            ├── asset-detail/
            ├── income/
            ├── settings/
            └── not-found/
```

### 3.1. Правила слоёв

- [ ] `core` не импортирует `features`.
- [ ] `shared` не знает о бизнес-сервисах фич; принимает данные через `input()`.
- [ ] `features` оркестрируют сервисы, состояние и UI.
- [ ] `layout` содержит только оболочку и навигацию.
- [ ] Компоненты standalone, без NgModule.
- [ ] Все компоненты `ChangeDetectionStrategy.OnPush`.
- [ ] Сервисы — `providedIn: 'root'`, кроме page-scoped state (если появится).
- [ ] Никаких прямых `HttpClient` вызовов из компонентов: только через `core/services`.

### 3.2. API-клиент

- [ ] `ApiClient` инкапсулирует `HttpClient`, base URL `/api`, query params и типизацию.
- [ ] Никаких `any` в публичных методах; типы — из `schema.ts`.
- [ ] Ошибки нормализуются в `ApiError`.
- [ ] Для скачивания файлов — отдельный метод с `observe: 'response'`, `responseType: 'blob'`.
- [ ] Для отмены устаревших запросов (period switch) — `switchMap`/`AbortSignal`, чтобы не перезаписывать свежие данные старым ответом.

### 3.3. Модели

- [ ] Сгенерировать `schema.ts` из OpenAPI.
- [ ] В `models.ts` сделать удобные алиасы:

```ts
import type { components } from './schema';

export type Health = components['schemas']['HealthResponse'];
export type Portfolio = components['schemas']['PortfolioResponse'];
export type Asset = components['schemas']['AssetDetail'];
export type AssetListItem = components['schemas']['AssetListItem'];
export type Position = components['schemas']['PositionItem'];
export type Operation = components['schemas']['OperationResponse'];
export type Income = components['schemas']['IncomeItem'];
export type Dashboard = components['schemas']['DashboardResponse'];
export type Settings = components['schemas']['SettingsResponse'];
export type Quote = components['schemas']['QuoteItem'];
```

- [ ] Не редактировать `schema.ts` вручную.
- [ ] Для ошибки добавить клиентский тип, потому что error envelope не входит в OpenAPI:

```ts
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}
```

## 4. Интеграция с API

### 4.1. Базовые правила

- [ ] Base URL в dev — `/api` через proxy; в prod — same origin.
- [ ] Строковые деньги не парсить для расчётов; форматировать через `Intl.NumberFormat`.
- [ ] Даты `YYYY-MM-DD` не пропускать через `new Date()` без необходимости.
- [ ] Периоды дашборда и истории передавать на server-side query, не фильтровать массив на клиенте.
- [ ] Не считать `market_value`, `invested`, `share`, `expected_coupons`, `income_paid_total` на клиенте.
- [ ] Не считать `price_rub` для облигации на клиенте; показывать `price_rub` из ответа.
- [ ] Списки не пагинировать; API не поддерживает pagination.
- [ ] Все запросы типизировать; response mapping не должен менять деньги/даты.

### 4.2. Сервисы и endpoint'ы

| Сервис | Методы API |
|---|---|
| `HealthService` | `GET /api/health` |
| `PortfolioService` | `GET /api/portfolio`, `PATCH /api/portfolio` |
| `AssetsService` | `GET /api/assets`, `GET /api/assets/search`, `POST /api/assets`, `GET /api/assets/{asset_id}`, `POST /api/assets/{asset_id}/refresh`, `DELETE /api/assets/{asset_id}` |
| `OperationsService` | `GET /api/operations`, `POST /api/operations`, `PATCH /api/operations/{operation_id}`, `DELETE /api/operations/{operation_id}` |
| `PositionsService` | `GET /api/positions` |
| `IncomeService` | `GET /api/income`, `POST /api/income`, `PATCH /api/income/{income_id}`, `POST /api/income/{income_id}/mark-paid`, `DELETE /api/income/{income_id}` |
| `DashboardService` | `GET /api/dashboard`, `GET /api/snapshots` |
| `QuotesService` | `GET /api/quotes/{asset_id}/history`, `POST /api/quotes/refresh`, `POST /api/quotes/manual` |
| `SettingsService` | `GET /api/settings`, `PATCH /api/settings` |
| `SystemService` | `POST /api/backup`, `GET /api/export` |

### 4.3. Обработка ошибок

- [ ] `api-error.interceptor.ts` ловит `HttpErrorResponse`.
- [ ] Если тело соответствует `ApiErrorBody`, создать `ApiError` с `status`, `code`, `message`, `details`.
- [ ] Если сеть недоступна — клиентский код `NETWORK_ERROR` (не backend-код), сообщение «Нет связи с backend».
- [ ] Если тело не JSON — `UNKNOWN_ERROR`.
- [ ] Не показывать stack trace и сырой JSON пользователю.
- [ ] Для `422` разобрать `details.errors[]` и подсветить поля формы.
- [ ] Для `409` показывать `message` и, где есть, `details.available`.
- [ ] Для blob-запросов экспорта ошибка приходит как `Blob`; в сервисе/interceptor прочитать его как текст и попытаться распарсить envelope, иначе показать общий текст.

```ts
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}
```

### 4.4. Паттерн состояния страницы

```ts
readonly data = signal<Dashboard | null>(null);
readonly loading = signal(false);
readonly error = signal<ApiError | null>(null);

async load(period: Period): Promise<void> {
  this.loading.set(true);
  this.error.set(null);
  try {
    this.data.set(await firstValueFrom(this.dashboard.get(period)));
  } catch (error) {
    this.error.set(toApiError(error));
  } finally {
    this.loading.set(false);
  }
}
```

- [ ] Signals для данных, загрузки и ошибки.
- [ ] `computed` — только для UI-производных (пусто/не пусто, фильтр по типу, флаг «есть partial»).
- [ ] Мутации: сервис → toast → reload затронутого экрана.
- [ ] Не держать глобальный store; каждый экран загружает нужные данные.
- [ ] После создания операции/дохода перезагружать позиции, дашборд и карточку актива при возврате.
- [ ] Для period switch использовать `switchMap` или проверку sequence id, чтобы late response не перетёр свежий.

## 5. Маршрутизация

| Путь | Компонент | Загрузка | Заголовок |
|---|---|---|---|
| `/dashboard` | `DashboardPage` | lazy `loadComponent` | Дашборд |
| `/portfolio` | `PortfolioPage` | lazy `loadComponent` | Портфель |
| `/assets/:id` | `AssetDetailPage` | lazy `loadComponent` | Карточка актива |
| `/income` | `IncomePage` | lazy `loadComponent` | Доходы |
| `/settings` | `SettingsPage` | lazy `loadComponent` | Настройки |
| `''` | redirect → `/dashboard` | — | — |
| `**` | `NotFoundPage` | lazy `loadComponent` | Страница не найдена |

```ts
export const routes: Routes = [
  {
    path: '',
    component: ShellComponent,
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        title: 'Дашборд',
        loadComponent: () =>
          import('./features/dashboard/dashboard-page').then((m) => m.DashboardPage),
      },
      {
        path: 'portfolio',
        title: 'Портфель',
        loadComponent: () =>
          import('./features/portfolio/portfolio-page').then((m) => m.PortfolioPage),
      },
      {
        path: 'assets/:id',
        title: 'Карточка актива',
        loadComponent: () =>
          import('./features/asset-detail/asset-detail-page').then((m) => m.AssetDetailPage),
      },
      {
        path: 'income',
        title: 'Доходы',
        loadComponent: () =>
          import('./features/income/income-page').then((m) => m.IncomePage),
      },
      {
        path: 'settings',
        title: 'Настройки',
        loadComponent: () =>
          import('./features/settings/settings-page').then((m) => m.SettingsPage),
      },
      {
        path: '**',
        title: 'Страница не найдена',
        loadComponent: () =>
          import('./features/not-found/not-found-page').then((m) => m.NotFoundPage),
      },
    ],
  },
];
```

- [ ] `provideRouter(routes, withComponentInputBinding())`.
- [ ] `:id` читать через `input()`/`ActivatedRoute`; при смене id перезагружать данные.
- [ ] Навигация в sidebar: Дашборд, Портфель, Доходы, Настройки.
- [ ] Активная ссылка — `routerLinkActive`.
- [ ] На мобильном — выпадающее меню/навигация (slide-down), без постоянного sidebar.

## 6. Ошибки, загрузка, пустые состояния, уведомления

### 6.1. Стратегия

| Ситуация | UI |
|---|---|
| Первичная загрузка | Skeleton/ProgressSpinner в области контента; не блокировать весь layout |
| Ошибка загрузки | Inline `ErrorState` с сообщением и кнопкой «Повторить» |
| Пустой список | `EmptyState` с CTA (например, «Добавить актив») |
| Мутация успешна | Toast success + reload |
| Мутация отклонена | Toast error с `message`; для 422 — inline ошибки полей |
| Долгая операция (refresh) | Loading на кнопке, disable, текст «Обновляем…» |
| 409 refresh | Информационный toast «Обновление уже выполняется» |
| Нет сети | ErrorState/Toast «Нет связи с backend» |

### 6.2. Toast

- [ ] Подключить `MessageService` и `<p-toast>` в shell.
- [ ] Success — коротко, без технических деталей.
- [ ] Error — `error.message`; при наличии `details` — не показывать весь объект, только понятные поля.
- [ ] Не показывать toast на каждый HTTP-запрос; только на действия пользователя.

### 6.3. Подтверждения

- [ ] `ConfirmationService` + `<p-confirmdialog>`.
- [ ] Подтверждать: удаление операции, удаление дохода, удаление актива, подтверждение выплаты купона.
- [ ] В тексте удаления операции предупреждать: «Если после удаления история станет некорректной, backend отклонит операцию».
- [ ] В тексте удаления актива: «Удалить можно только актив без операций и выплаченных доходов».

## 7. Dev proxy и production

### 7.1. Dev

`proxy.conf.json`:

```json
{
  "/api": {
    "target": "http://127.0.0.1:8000",
    "secure": false,
    "changeOrigin": true,
    "logLevel": "info"
  }
}
```

`angular.json`:

```json
{
  "serve": {
    "options": {
      "proxyConfig": "proxy.conf.json"
    }
  }
}
```

- [ ] `npm start` → `http://localhost:4200`.
- [ ] Frontend обращается к `/api/...`, proxy уходит на `127.0.0.1:8000`.
- [ ] CORS в dev не обязателен при proxy, но backend уже разрешает `localhost:4200` и `127.0.0.1:4200`.

### 7.2. Production

- [ ] `ng build` с production-конфигурацией.
- [ ] Output: repo-root `dist/browser` (`D:\Work\ai test\dist\browser`); в `angular.json` задать `"outputPath": { "base": "../dist" }` (без этого Angular 20 положит сборку в `frontend/dist/<project>/browser`).
- [ ] FastAPI раздаёт статику после API-роутов.
- [ ] SPA fallback: неизвестные не-API пути возвращают `index.html`.
- [ ] `/api/*`, `/docs`, `/openapi.json` не должны попадать в fallback.
- [ ] Хэшированные assets кэшировать надолго; `index.html` — no-cache.

Вариант реализации (Stage 6):

```python
# backend/app/main.py — только статика, API-контракт не меняется
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse

DIST_DIR = (Path(__file__).resolve().parents[2] / "dist" / "browser").resolve()

if DIST_DIR.is_dir():
    # 1. Сначала API и docs (они уже добавлены выше).
    # 2. Затем catch-all для SPA, но не для /api, /docs и /openapi.json.
    @application.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        if full_path in {"docs", "openapi.json"} or full_path.startswith("docs/"):
            raise HTTPException(status_code=404)

        candidate = (DIST_DIR / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(DIST_DIR):
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
```

Если используется `StaticFiles`, нужен subclass с fallback на `index.html` для 404, иначе deep links (`/assets/1`) получат JSON 404. В любом варианте проверить:

- [ ] `/` → SPA.
- [ ] `/dashboard` → SPA.
- [ ] `/assets/1` → SPA.
- [ ] `/api/health` → JSON.
- [ ] `/docs` → Swagger.
- [ ] `/openapi.json` → OpenAPI.

### 7.3. `start.ps1`

Скрипт в корне репозитория:

- [ ] Проверяет наличие `uv`; если нет — использует `python -m uv`.
- [ ] Выполняет `alembic upgrade head` в `backend`.
- [ ] Если нет `dist/browser/index.html` или передан `-Build` — выполняет `npm ci` (если нужно) и `npm run build` в `frontend`.
- [ ] Запускает `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- [ ] Опционально открывает `http://127.0.0.1:8000`.
- [ ] Понятно сообщает, если Node/npm не установлены.

```powershell
param([switch]$Build)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCommand) {
    $uvExe = 'uv'
    $uvArgs = @()
} else {
    $uvExe = 'python'
    $uvArgs = @('-m', 'uv')
}

Push-Location (Join-Path $root 'backend')
& $uvExe @uvArgs run alembic upgrade head
Pop-Location

$distIndex = Join-Path $root 'dist\browser\index.html'
if ($Build -or -not (Test-Path $distIndex)) {
    Push-Location (Join-Path $root 'frontend')
    npm ci
    npm run build
    Pop-Location
}

Push-Location (Join-Path $root 'backend')
& $uvExe @uvArgs run uvicorn app.main:app --host 127.0.0.1 --port 8000
Pop-Location
```

Скрипт — ориентир; при реализации проверить splatting `@uvArgs` в PowerShell 5.1/7 и не запускать `npm ci` при каждом старте без необходимости.

## 8. Этапы

### [x] Этап 0. Каркас, shell, тема, routing, proxy, API foundation

**Цель:** приложение запускается, выглядит как светлая русская оболочка, ходит в `/api/health` через proxy, имеет типы, форматтеры и базовые UI-компоненты.

**Deliverables**

- [x] Создан `frontend/` через Angular CLI 20.3.42: standalone, routing, SCSS, npm.
- [x] В `package.json` добавлен скрипт `"api:types": "openapi-typescript http://127.0.0.1:8000/openapi.json -o src/app/core/api/schema.ts"`; тесты запускаются командой `npm test -- --watch=false --browsers=ChromeHeadless`.
- [x] Зафиксированы точные версии: Angular `20.3.34`, Angular CLI/build `20.3.42`, `@angular/cdk` `20.2.14`, PrimeNG `20.4.0`, `@primeuix/themes` `2.0.0`, PrimeIcons `7.0.0`, Chart.js `4.4.9`, TypeScript `5.9.3`, RxJS `7.8.2`, Zone.js `0.15.1`, Karma + Jasmine (`@angular/build:karma`).
- [x] PrimeNG 20.4.0 (MIT) установлен без license key; `providePrimeNG` без поля `license`.
- [x] Настроены `providePrimeNG` Aura light, `provideHttpClient`, `provideRouter`, `MessageService`, `ConfirmationService`.
- [x] Использовать kebab-case селекторы PrimeNG 20 (`p-select`, `p-table`, `p-dialog`); CamelCase-варианты не использовать.
- [x] Глобальные стили: Aura preset из `@primeuix/themes`, PrimeIcons, reset, типографика, layout-токены, светлая тема.
- [x] Shell: sticky topbar, desktop sidebar, responsive mobile navigation, router-outlet, toast, confirm dialog.
- [x] Маршруты из §5 с lazy `loadComponent`.
- [x] `proxy.conf.json` и `angular.json` serve options; production output — repo-root `dist/browser` (`outputPath.base = "../dist"`).
- [x] `core/api`: `ApiClient`, `ApiError`, `api-error.interceptor`.
- [x] `schema.ts` сгенерирован; `models.ts` с алиасами.
- [x] Форматтеры/пайпы: money, price, percent, share, date-time; unit-тесты.
- [x] Shared UI: page-header, stat-card, empty-state, error-state, loading-skeleton, period-switcher, price-source-badge.
- [x] `README.md` frontend: установка, запуск, тесты, генерация типов.

**Files/areas**

```text
frontend/angular.json
frontend/package.json
frontend/proxy.conf.json
frontend/src/styles.scss
frontend/src/app/app.config.ts
frontend/src/app/app.routes.ts
frontend/src/app/layout/**
frontend/src/app/core/api/**
frontend/src/app/core/formatting/**
frontend/src/app/shared/ui/**
```

**API endpoints:** `GET /api/health` (проверка proxy).

**Acceptance criteria**

- [x] `npm ci` устанавливает зависимости с чистого `package-lock.json`.
- [x] `npm start` открывает `http://localhost:4200`, shell отображается без ошибок в консоли.
- [x] Переходы по всем маршрутам работают, активный пункт подсвечен.
- [x] `GET /api/health` через proxy возвращает `status=ok`.
- [x] Тема светлая, Aura, русские подписи, нет тёмного режима.
- [x] `npm run build` проходит.
- [x] `npm test -- --watch=false --browsers=ChromeHeadless` проходит (shell + pipes); `CHROME_BIN` указывает на Edge/Chrome.
- [x] Нет `any` в API-клиенте, нет бизнес-расчётов.

**Tests**

- [x] Unit: `MoneyPipe`, `PricePipe`, `PercentPipe`, `SharePipe`, `DatePipe`.
- [x] Unit: `ApiError` mapping для envelope, network error, unknown error.
- [x] Component: `ShellComponent` рендерит навигацию и router-outlet, мобильный toggle.
- [x] Smoke: `App` создаётся; `HttpTestingController` не имеет неожиданных запросов.

**Review checkpoint**

- [x] Ревью архитектуры: слои, standalone, OnPush, отсутствие NgModule.
- [x] Ревью темы: Aura, 16px base, контраст, отсутствие тёмной темы.
- [x] Ревью версий: PrimeNG 20.4.0 и `@primeuix/themes` 2.0.0 запинены (MIT), license key отсутствует.
- [x] Ревью тестового раннера: Karma + Jasmine через `@angular/build:karma` (без `karma.conf.js`), `npm test -- --watch=false --browsers=ChromeHeadless`.
- [x] Ревью API-клиента: типы, ошибки, отсутствие бизнес-логики.

**Review findings / status:** **PASS** — независимое ревью после миграции на Angular **20.3.34** + PrimeNG **20.4.0** (MIT) / `@primeuix/themes` **2.0.0**: **0 Critical, 0 Required**. Закрыты находки: **R1** — `aria-current="page"` и активный раздел выводятся из `activeSection`, `/assets/:id` относится к «Портфелю»; **R2** — smoke-тест `AppComponent` с реальными маршрутами, `provideHttpClientTesting()` и `http.verify()`; **R3** — production output repo-root `dist/browser`; **R4** — sidebar и мобильное меню используют единый active-state без дублирования; **R5** — обоснование MIT-линии PrimeNG 20 / themes 2.0.0 зафиксировано, license key не требуется. Финально: **70 Karma-тестов** (64 базовых + 6 edge-case тестов `navigation.ts`) в Chrome headless (Edge через `CHROME_BIN`), `npm run build`, `npm audit --omit=dev` — **0 vulnerabilities**. `GET /api/health` через dev-proxy вернул `200`/`status=ok`; shell и все маршруты отрисованы в headless-браузере. Визуальные pixel-проверки 360/768/1280 и полный a11y-аудит осознанно отложены до Stage 5; non-blocking nits: сгенерированный `schema.ts` содержит повреждённую кодировку комментариев backend (на типы не влияет), базовые стили Aura 16px требуют визуальной проверки на малых экранах.

Заметки по реализации:

- PrimeNG **19–21 — MIT**, **22+ — коммерческая лицензия**; проект остаётся на MIT-линии 20.4.0. Angular 20.3.34 — текущая поддерживаемая линия; прежний scaffold на устаревшей линии имел security advisories, поэтому пересобран.
- Shell: sticky topbar + desktop sidebar (≥ 901 px), мобильное slide-down меню (hamburger, `aria-expanded`, Escape, закрытие при переходе в desktop). Активный раздел и `aria-current` выводятся из одного `activeSection` signal (router events); `/assets/:id` относится к «Портфелю».
- Добавлены регрессионные тесты: активная навигация `/assets/1` → `/portfolio`; smoke `AppComponent` с реальными маршрутами, `provideHttpClientTesting()` и проверкой `http.verify()`.
- `ApiClient.post` по умолчанию отправляет `{}` (не `null`); добавлен `SharePipe` для долей (`0.2789` → `27,89 %`); `DatePipe` нормализует ISO-дроби длиннее миллисекунд; `.p-confirmdialog` приведён к фактическому классу PrimeNG.
- Сгенерированный `schema.ts` содержит комментарии backend с нарушенной кодировкой исходников; на типы и работу приложения не влияет.

---

### [x] Этап 1. Data layer + Dashboard

**Цель:** дашборд показывает реальные данные seed: итоги, график, позиции, ближайшие купоны, partial/stale-состояния.

**Deliverables**

- [x] Типы и сервисы: Dashboard, Positions (для портфеля), Portfolio, Health.
- [x] `DashboardPage`: заголовок, 5 карточек, period switcher, график, таблица позиций, ближайшие купоны.
- [x] Карточки: стоимость, вложено, выплаченные дивиденды, выплаченные купоны, ожидаемые купоны.
- [x] Period switch: `1M`, `3M`, `1Y`, `ALL`; запрос `GET /api/dashboard?period=...`.
- [x] Переключатель периода меняет только текущий вид; сохранённый default `dashboard_period` редактируется на экране настроек.
- [x] Первичная загрузка — `GET /api/dashboard` без `period`: backend применит сохранённый `dashboard_period`, активная кнопка берётся из `response.period`.
- [x] Chart.js: две линии (market_value, invested), даты по X, tooltip ru-RU, легенда.
- [x] Таблица позиций: тикер, тип, количество, средняя, текущая цена, стоимость, доля; ссылка на карточку. Использовать `dashboard.positions`, без отдельного запроса.
- [x] Ближайшие купоны: дата, тикер, сумма, количество; ссылка в доходы.
- [x] Partial warning при `is_partial=true`; stale badge по `is_stale`/`price_source`.
- [x] Empty state для пустого портфеля; error state с retry; skeleton.
- [x] Chart wrapper `ValueChartComponent` в `shared/ui`, чтобы изолировать Chart.js; импортировать `ChartModule` из `primeng/chart`, типы — из `chart.js`.

**Files/areas**

```text
frontend/src/app/core/services/dashboard.service.ts
frontend/src/app/core/services/positions.service.ts
frontend/src/app/core/services/portfolio.service.ts
frontend/src/app/core/services/settings.service.ts
frontend/src/app/features/dashboard/**
frontend/src/app/shared/ui/stat-card/**
frontend/src/app/shared/ui/period-switcher/**
frontend/src/app/shared/ui/value-chart/**
```

**API endpoints**

- `GET /api/dashboard?period=1M|3M|1Y|ALL`
- `GET /api/portfolio`
- `GET /api/health` (для индикатора, опционально)

**Acceptance criteria**

- [x] С seed дашборд показывает `16242.00`, `15918.45`, `200.00`, `525.00`, `1575.00`.
- [x] Позиции: SBER 15 @110, ОФЗ 15 @95.123%, доли `0.2789`/`0.7211`.
- [x] Ближайшие купоны: 3 записи по `525.00`.
- [x] Переключение периода меняет `series` и не меняет `totals`.
- [x] При `is_partial=true` виден warning; при `is_stale=true` виден бейдж с датой.
- [x] Нет клиентского пересчёта итогов, долей, купонов.
- [x] Пустой портфель показывает EmptyState, ошибка — ErrorState с retry.

**Tests**

- [x] Unit: `DashboardService` формирует корректный URL с period; первичный запрос идёт без `period`.
- [x] Unit: mapping `Dashboard` не теряет строковые деньги и `is_partial`.
- [x] Component: карточки рендерят значения; period switch вызывает сервис с нужным периодом.
- [x] Component: partial warning и stale badge.
- [x] Component: empty/error/loading states.
- [x] Chart: замокать `ValueChartComponent` или canvas context; не требовать реального canvas HTML в Karma/headless-браузере.

**Review checkpoint**

- [x] Ревью контракта: поля совпадают с OpenAPI.
- [x] Ревью расчётов: на клиенте нет арифметики денег.
- [x] Ревью графика: данные не агрегируются/не интерполируются; series из API выводится точка-в-точку.
- [x] Ревью состояний: loading/empty/error/partial/stale.

**Review findings / status:** **PASS после исправлений** — 2026-11-01, ревью по skill `code-review-and-quality`. Исправлено в ходе ревью: (R1) `DashboardResponse.period` приходит строкой, `as Period` убран; добавлен runtime guard `toPeriod()` и fallback на предыдущий период + тесты на неизвестный период; (R2) удалён мёртвый `trackPosition`; (R3) из таблицы убран англоязычный бейдж `RUB`/`PERCENT` — цена уже подписана `₽`/`%`; (R4) график больше не сглаживается (`tension: 0`), данные не интерполируются; (R5) исправлена высота `p-chart` (canvas заполняет 320 px, а не 147 px) и переполнение подписей X на 360 px (`autoSkipPadding`, без принудительного `maxTicksLimit`). Добавлен регрессионный тест на late response: ответ устаревшего периода не перезаписывает свежий. Проверки: **95 Karma-тестов** в Chrome headless (Edge через `CHROME_BIN`), `npm run build`, живая проверка seeded API (`16242.00`/`15918.45`/`200.00`/`525.00`/`1575.00`, series 183 точки, SBER/ОФЗ, 3 купона, `is_stale=true` для обеих позиций). Headless-проверка 1280 px и 360 px: горизонтального скролла страницы нет, `scrollWidth=viewport`; консоль без ошибок и NG0100. Mutation-проверка: отключение sequence guard и отключение partial warning роняют по одному тесту. Осознанно отложено до Stage 5: caption/aria-label таблиц, клавиатурный focus в диалогах, полный a11y-аудит; горизонтальный скролл широкой таблицы позиций на узких экранах — намеренный.

---

### [ ] Этап 2. Portfolio, asset search/add, asset detail, operations CRUD

**Цель:** можно добавить актив, открыть карточку, создать/изменить/удалить BUY/SELL, увидеть корректную позицию и обработать ошибки.

**Deliverables**

- [ ] `PortfolioPage`: список позиций, фильтр «Все / Акции / Облигации», итоги, кнопка «Добавить актив».
- [ ] Фильтр типа — клиентский по `asset.type`; данные не перезапрашиваются.
- [ ] Диалог поиска MOEX: debounce 300–500 мс, запрос `GET /api/assets/search?q=`, результаты, кнопка «Добавить».
- [ ] Добавление: `POST /api/assets` с `{secid, board}`; обработка `409 ASSET_ALREADY_EXISTS`, `502 MOEX_*`.
- [ ] Сравнение результатов поиска с локальными активами, чтобы показать «уже добавлен».
- [ ] `AssetDetailPage`: карточка актива, позиция, операции, доходы, история цен, кнопка refresh, удаление.
- [ ] Позиция в карточке — из `GET /api/positions` по `asset.id` (отдельного endpoint нет); если позиции нет — показать «Нет открытой позиции» и CTA «Добавить операцию».
- [ ] История операций — `GET /api/operations?asset_id=`.
- [ ] Доходы — `GET /api/income?asset_id=`; в карточке разделить на выплаченные и ожидаемые (два запроса с `status` или группировка по `status` без пересчёта сумм).
- [ ] График цены — `GET /api/quotes/{asset_id}/history?period=1Y` (опционально, если успеваем; Chart wrapper уже есть).
- [ ] Диалог операции: create/edit, BUY/SELL, дата, количество, цена, note.
- [ ] Для облигации — переключатель `RUB`/`PERCENT`; подпись текущего номинала.
- [ ] Валидация формы: quantity integer > 0; price > 0, до 6 знаков; дата обязательна.
- [ ] `PATCH` только изменённых полей; `DELETE` с подтверждением.
- [ ] Обработка `409 INSUFFICIENT_QUANTITY` с `available`/`requested`; `400` — сообщение backend; `422` — поля.
- [ ] `POST /api/assets/{asset_id}/refresh` — кнопка с loading; `502` — toast.
- [ ] `DELETE /api/assets/{asset_id}` — confirm; `409 ASSET_IN_USE` — объяснение; `204` — возврат в портфель.
- [ ] Не считать `price_rub`, среднюю и стоимость на клиенте; показывать ответы API.

**Files/areas**

```text
frontend/src/app/features/portfolio/**
frontend/src/app/features/asset-detail/**
frontend/src/app/core/services/assets.service.ts
frontend/src/app/core/services/operations.service.ts
frontend/src/app/core/services/positions.service.ts
frontend/src/app/core/services/income.service.ts
frontend/src/app/core/services/quotes.service.ts
frontend/src/app/shared/ui/confirm-dialog/**
```

**API endpoints**

- `GET /api/assets`
- `GET /api/assets/search?q=`
- `POST /api/assets`
- `GET /api/assets/{asset_id}`
- `POST /api/assets/{asset_id}/refresh`
- `DELETE /api/assets/{asset_id}`
- `GET /api/operations?asset_id=`
- `POST/PATCH/DELETE /api/operations`
- `GET /api/positions`
- `GET /api/income?asset_id=`
- `GET /api/quotes/{asset_id}/history?period=`

**Acceptance criteria**

- [ ] Портфель показывает SBER и ОФЗ, фильтр «Акции» оставляет SBER, «Облигации» — ОФЗ.
- [ ] Поиск «SBER» (при сети) находит бумагу; повторное добавление даёт понятную ошибку.
- [ ] Карточка SBER: 15 шт., средняя 110, стоимость 4530, операции 3.
- [ ] Карточка ОФЗ: 15 шт., 95.123%, номинал 800, амортизация 200, операции 1.
- [ ] Покупка 5 @300 обновляет позицию после reload; отдельный сценарий: продажа 20 при исходном остатке 15 показывает «доступно 15».
- [ ] Операция облигации в PERCENT сохраняется; `price_rub` рассчитывается по номиналу на дату сделки (например, 97.6% при номинале 800 → `780.80`).
- [ ] Редактирование и удаление операции работают; удаление, ломающее историю, показывает 409.
- [ ] Удаление актива с операциями блокируется с понятным сообщением.
- [ ] Нет клиентских расчётов денег.

**Tests**

- [ ] Unit: `AssetsService.search` debounce/URL, `OperationsService` payload для BUY/SELL и bond PERCENT.
- [ ] Unit: маппинг `INSUFFICIENT_QUANTITY` в `ApiError` с `available`.
- [ ] Component: фильтр портфеля.
- [ ] Component: форма операции — обязательные поля, quantity/price, переключатель PERCENT для облигации.
- [ ] Component: 409 oversell показывает сообщение и не закрывает диалог.
- [ ] Component: confirm удаления; 204 закрывает/навигирует; 409 остаётся.
- [ ] Component: asset detail загружает asset/positions/operations/income.

**Review checkpoint**

- [ ] Ревью форм: Reactive Forms, валидаторы, ошибки полей.
- [ ] Ревью операций: нет клиентской нормализации цены; payload соответствует API.
- [ ] Ревью destructive actions: confirm, обработка 409, reload.
- [ ] Ревью MOEX-зависимых сценариев: offline/502, retry, отсутствие бесконечных повторов.

**Review findings / status:** _не заполнено; заполняется после ревью._

---

### [ ] Этап 3. Income

**Цель:** экран доходов с вкладками, фильтрами, ручным добавлением, подтверждением купона, редактированием и удалением.

**Deliverables**

- [ ] `IncomePage` с вкладками «Выплаченные» / «Ожидаемые купоны».
- [ ] Запрос `GET /api/income?status=PAID|EXPECTED`; смена вкладки меняет `status`.
- [ ] Фильтры: `kind` (DIVIDEND/COUPON), `asset_id`, `from`, `to`; кнопка «Сбросить».
- [ ] Таблица: дата выплаты, тикер, тип, статус, количество, сумма за единицу, итог, источник, overdue.
- [ ] Карточка итогов: дивиденды, купоны, ожидаемые купоны; подпись «По всему портфелю».
- [ ] Диалог ручного дохода: kind, asset, amount_total, pay_date, quantity (optional), amount_per_unit (optional), record_date (optional), note.
- [ ] `POST /api/income`; всегда PAID; после успеха — reload и toast.
- [ ] Редактирование PAID: amount_total, quantity, pay_date, note; total авторитетен.
- [ ] Подтверждение EXPECTED: диалог с prefill `amount_total` и `pay_date`; `POST /mark-paid`.
- [ ] Обработка `409 INCOME_ALREADY_PAID`; reload.
- [ ] Редактирование EXPECTED: только note/record_date; не показывать редактирование суммы/даты, если backend их запрещает.
- [ ] Удаление дохода с confirm; EXPECTED — предупреждение, что MOEX может синхронизировать снова.
- [ ] Overdue badge для `is_overdue=true`.
- [ ] EmptyState для каждой вкладки; ErrorState с retry.

**Files/areas**

```text
frontend/src/app/features/income/**
frontend/src/app/core/services/income.service.ts
frontend/src/app/core/services/assets.service.ts
frontend/src/app/shared/ui/stat-card/**
```

**API endpoints**

- `GET /api/income?status=&kind=&asset_id=&from=&to=`
- `POST /api/income`
- `PATCH /api/income/{income_id}`
- `POST /api/income/{income_id}/mark-paid`
- `DELETE /api/income/{income_id}`
- `GET /api/assets` (для select)

**Acceptance criteria**

- [ ] Вкладка PAID показывает дивиденд `200.00` и купон `525.00`.
- [ ] Вкладка EXPECTED показывает 3 купона по `525.00`, итог `1575.00`.
- [ ] Фильтр по облигации/типу работает; totals не меняются и подписаны как портфельные.
- [ ] Ручной дивиденд `150.00` появляется в PAID.
- [ ] Mark-paid переводит EXPECTED в PAID; повторный вызов показывает 409.
- [ ] Редактирование суммы PAID обновляет `amount_per_unit`.
- [ ] Удаление работает; overdue отображается.
- [ ] Нет клиентского расчёта суммы купона.

**Tests**

- [ ] Unit: `IncomeService.list` формирует query params; mark-paid payload.
- [ ] Unit: обработка `INCOME_ALREADY_PAID`.
- [ ] Component: переключение вкладок и фильтры.
- [ ] Component: форма ручного дохода (обязательные поля).
- [ ] Component: mark-paid prefill и успешный reload.
- [ ] Component: overdue badge; totals label.

**Review checkpoint**

- [ ] Ревью семантики PAID/EXPECTED: total авторитетен, expected нельзя редактировать как paid.
- [ ] Ревью filters/totals: totals портфельные, не фильтрованные.
- [ ] Ревью ошибок 409/422.
- [ ] Ревью UX подтверждения выплаты.

**Review findings / status:** _не заполнено; заполняется после ревью._

---

### [ ] Этап 4. Settings/system

**Цель:** экран настроек и системных операций: health, refresh, настройки, backup, экспорт.

**Deliverables**

- [ ] `SettingsPage`: health card (status, version, database, moex, last refresh).
- [ ] Кнопка «Обновить котировки» → `POST /api/quotes/refresh`; loading, disable, результат `updated/failed/errors`.
- [ ] После refresh — reload health, dashboard, positions.
- [ ] Обработка `409 REFRESH_IN_PROGRESS` и частичных ошибок `errors[]`.
- [ ] Переключатель `quote_refresh_enabled`; `PATCH /api/settings`; при `400` — revert + объяснение master-switch.
- [ ] Select `dashboard_period` (`1M/3M/1Y/ALL`); `PATCH /api/settings`; helper text, что это default для дашборда.
- [ ] Кнопка «Создать backup» → `POST /api/backup`; показать `path`, `size_bytes`, `created_at`; пояснить, что файл не скачивается по HTTP.
- [ ] Кнопки «Экспорт JSON» и «Экспорт CSV» → `GET /api/export?format=...`; blob + filename из `Content-Disposition`.
- [ ] Fallback имени файла, если заголовок недоступен.
- [ ] Empty/error/loading для системных карточек.
- [ ] Никаких секретов/ключей на экране.

**Files/areas**

```text
frontend/src/app/features/settings/**
frontend/src/app/core/services/health.service.ts
frontend/src/app/core/services/quotes.service.ts
frontend/src/app/core/services/settings.service.ts
frontend/src/app/core/services/system.service.ts
```

**API endpoints**

- `GET /api/health`
- `POST /api/quotes/refresh`
- `GET/PATCH /api/settings`
- `POST /api/backup`
- `GET /api/export?format=json|csv`

**Acceptance criteria**

- [ ] Health показывает `status=ok`, `version=0.1.0`, `database=ok`; `moex` — `unknown`/`ok`/`error` в зависимости от последнего refresh (в offline seed обычно `unknown` или `error`).
- [ ] Refresh с сетью обновляет статус; без сети показывает ошибку/частичный результат, не падает.
- [ ] Повторный refresh во время выполнения показывает 409-сообщение.
- [ ] Переключение `dashboard_period` сохраняется и влияет на дашборд без query.
- [ ] При env-master-switch `false` включение auto-refresh показывает 400 и возвращает switch.
- [ ] Backup показывает путь/размер/время.
- [ ] JSON и CSV скачиваются с правильными именами; CSV — ZIP.
- [ ] Нет попытки скачать backup по HTTP.

**Tests**

- [ ] Unit: `SettingsService.patch` отправляет только изменённые поля.
- [ ] Unit: `SystemService.export` читает `Content-Disposition`.
- [ ] Component: master-switch 400 → revert + toast.
- [ ] Component: refresh 409 и частичные errors.
- [ ] Component: backup result отображается.
- [ ] Component: export создаёт blob и ссылку (mock `URL.createObjectURL`).

**Review checkpoint**

- [ ] Ревью master-switch семантики.
- [ ] Ревью скачивания: blob, filename, revoke, ошибки.
- [ ] Ревью длительных операций: loading, disable, отсутствие параллельных refresh.
- [ ] Ревью безопасности: нет ключей/путей, кроме backup path.

**Review findings / status:** _не заполнено; заполняется после ревью._

---

### [ ] Этап 5. UX polish, responsive, accessibility, ru-RU, E2E

**Цель:** приложение удобно на телефоне и десктопе, доступно с клавиатуры, полностью на русском, со всеми состояниями.

**Deliverables**

- [ ] Адаптивность: 360px, 768px, 1280px+; sidebar → мобильное меню/навигация; таблицы скроллятся/переносятся.
- [ ] Карточки дашборда в сетке; график не ломает layout; длинные тикеры не переполняют.
- [ ] Все формы: labels, `aria-describedby`, inline errors, focus на первом невалидном поле.
- [ ] Диалоги: focus trap, Esc, возврат фокуса, `aria-modal`.
- [ ] Таблицы: caption/aria-label, сортировка доступна с клавиатуры.
- [ ] Контраст текста/бейджей; не полагаться только на цвет для stale/overdue.
- [ ] Русская локаль PrimeNG (datepicker, table, confirm) и `LOCALE_ID='ru-RU'`.
- [ ] Единые форматы денег/процентов/дат; склонения «купон/купона/купонов» (если нужно).
- [ ] Empty/error/loading на всех экранах; retry.
- [ ] Тосты и подтверждения не перекрывают контент на мобильном.
- [ ] Ручной E2E-сценарий:
  - [ ] seed;
  - [ ] дашборд — сверить суммы;
  - [ ] портфель — фильтр, карточка SBER/ОФЗ;
  - [ ] операция BUY/SELL, oversell 409;
  - [ ] доходы — mark-paid, ручной дивиденд;
  - [ ] настройки — refresh (если сеть), backup, экспорт;
  - [ ] перезагрузка страницы — данные сохранились.
- [ ] Проверка консоли: нет ошибок, нет NG0100/ExpressionChanged.
- [ ] Проверка клавиатуры: Tab/Shift+Tab, Enter, Esc.

**Files/areas**

```text
frontend/src/styles.scss
frontend/src/app/layout/**
frontend/src/app/shared/ui/**
frontend/src/app/features/**
```

**API endpoints:** без новых; используются все предыдущие.

**Acceptance criteria**

- [ ] Нет горизонтального скролла на 360px, кроме таблиц с явным scroll.
- [ ] Все интерактивные элементы доступны с клавиатуры.
- [ ] Все пользовательские тексты на русском.
- [ ] Все состояния (loading/empty/error/partial/stale/overdue) видны и понятны.
- [ ] Ручной E2E-сценарий проходит на seed.
- [ ] `npm run build` и `npm test -- --watch=false --browsers=ChromeHeadless` зелёные.

**Tests**

- [ ] Component: состояния loading/empty/error для ключевых экранов.
- [ ] Component: клавиатурный сценарий диалога (Esc/focus).
- [ ] Unit: локальные форматтеры/склонения.
- [ ] Ручной E2E по чек-листу выше.
- [ ] Опционально: Playwright smoke — позже, не блокер MVP.

**Review checkpoint**

- [ ] Ревью a11y: labels, focus, contrast, keyboard.
- [ ] Ревью responsive: 360/768/1280.
- [ ] Ревью локали: все строки, форматы, PrimeNG locale.
- [ ] Ревью состояний: нет «пустого экрана» без explanation.

**Review findings / status:** _не заполнено; заполняется после ревью._

---

### [ ] Этап 6. Production integration, final tests, docs

**Цель:** одной командой запускается production-приложение: FastAPI отдаёт API и собранный Angular, deep links работают.

**Deliverables**

- [ ] `ng build` production → repo-root `dist/browser/index.html` (`D:\Work\ai test\dist\browser`); в `angular.json` задать `"outputPath": { "base": "../dist" }` (по умолчанию Angular 20 кладёт сборку в `frontend/dist/<project>/browser`).
- [ ] Проверить размеры бандлов; при необходимости поднять budget или разделить чанки.
- [ ] FastAPI static serving + SPA fallback (см. §7.2), без изменений API-контракта.
- [ ] Проверить порядок routes: API/docs/openapi не перехватываются SPA.
- [ ] `start.ps1` в корне: миграции, сборка при необходимости, запуск.
- [ ] `.gitignore`: `frontend/node_modules`, `dist`, `.angular`, локальные env-файлы.
- [ ] `frontend/README.md`: запуск, тесты, генерация типов, production.
- [ ] Обновить `docs/FRONTEND_PLAN.md`: отметить этапы, добавить review findings.
- [ ] Обновить `docs/FRONTEND_HANDOFF.md`, если фактический контракт/команды уточнились.
- [ ] Финальный прогон:
  - [ ] `npm ci`;
  - [ ] `npm run build`;
  - [ ] `npm test -- --watch=false --browsers=ChromeHeadless`;
  - [ ] backend `pytest` (не менять тесты);
  - [ ] contract smoke: health, positions, dashboard, income, settings, backup, export.
- [ ] Финальное ревью по skill `code-review-and-quality`.

**Files/areas**

```text
start.ps1
backend/app/main.py            # только static/SPA
frontend/angular.json
frontend/README.md
docs/FRONTEND_PLAN.md
docs/FRONTEND_HANDOFF.md
.gitignore
```

**API endpoints:** все; production smoke.

**Acceptance criteria**

- [ ] `.\start.ps1` поднимает приложение на `http://127.0.0.1:8000`.
- [ ] `/` и `/dashboard` отдают SPA.
- [ ] `/assets/1` (deep link) отдаёт SPA, не 404.
- [ ] `/api/health` отдаёт JSON.
- [ ] `/docs` и `/openapi.json` работают.
- [ ] Скачивание JSON/CSV работает в production (same origin).
- [ ] `npm ci && npm run build && npm test -- --watch=false --browsers=ChromeHeadless` проходят с чистой установки (Angular 20.3.34, CLI/build 20.3.42, Karma + Jasmine через `@angular/build:karma`).
- [ ] Нет CORS-ошибок в production.
- [ ] README описывает запуск, сборку, тесты, seed, troubleshooting.

**Tests**

- [ ] `npm ci` с нуля.
- [ ] `npm run build`.
- [ ] `npm test -- --watch=false --browsers=ChromeHeadless`.
- [ ] Backend pytest (регресс).
- [ ] Contract smoke через `curl`/`Invoke-RestMethod`.
- [ ] Ручной smoke production: dashboard, portfolio, asset detail, income, settings, downloads, deep link, reload.

**Review checkpoint**

- [ ] Ревью production routing: API/docs не сломаны.
- [ ] Ревью static cache: hashed assets vs index.html.
- [ ] Ревью `start.ps1`: uv fallback, ошибки, повторный запуск.
- [ ] Ревью DoD и документации.
- [ ] Финальный verdict.

**Review findings / status:** _не заполнено; заполняется после ревью._

## 9. Тестовая стратегия

### 9.1. Unit

- [ ] Сервисы: корректные URL/params, mapping response, ошибки.
- [ ] `ApiError`/interceptor: envelope, network, unknown, 422 details.
- [ ] Папы/форматтеры: деньги, цены, проценты, даты, локаль.
- [ ] Утилиты: парсинг `Content-Disposition`, fallback filename.
- [ ] Валидаторы форм: quantity/price/date.

### 9.2. Component

- [ ] Dashboard: карточки, period switch, partial/stale, empty/error.
- [ ] Portfolio: фильтр, поиск/добавление, 409 duplicate.
- [ ] Asset detail: загрузка, операция, oversell, delete.
- [ ] Income: вкладки, фильтры, mark-paid, 409, overdue.
- [ ] Settings: master-switch 400, refresh 409, backup, export.
- [ ] Shell: навигация, мобильное меню, toast/confirm.

### 9.3. Contract / integration

- [ ] `openapi-typescript` генерирует типы без ошибок.
- [ ] Contract smoke против seeded backend:
  - [ ] `GET /api/health` 200;
  - [ ] `GET /api/positions` содержит SBER/ОФЗ;
  - [ ] `GET /api/dashboard?period=1Y` totals;
  - [ ] `GET /api/income?status=PAID|EXPECTED`;
  - [ ] `GET /api/settings`;
  - [ ] `POST /api/backup`;
  - [ ] `GET /api/export?format=json|csv`.
- [ ] Проверить строковые деньги в ответах (не number).

### 9.4. Build / CI

- [ ] `npm ci`.
- [ ] `npm run build`.
- [ ] `npm test -- --watch=false --browsers=ChromeHeadless` (Karma + Jasmine через `@angular/build:karma`, Chrome/Edge headless).
- [ ] Backend `pytest` как регресс.
- [ ] CI не требует MOEX; seed и mock.

### 9.5. E2E

- [ ] Ручной сценарий из Stage 5 обязателен.
- [ ] Playwright — опционально после MVP; не блокирует Definition of Done.

## 10. Definition of Done

- [ ] Все этапы 0–6 отмечены `[x]`.
- [ ] Все stage-level review checkpoints пройдены, findings закрыты или осознанно отложены.
- [ ] `npm ci` с чистой установки.
- [ ] `npm run build` без ошибок.
- [ ] `npm test -- --watch=false --browsers=ChromeHeadless` зелёный (Karma + Jasmine через `@angular/build:karma`; `CHROME_BIN` указывает на Edge/Chrome).
- [ ] Backend contract smoke на seeded БД.
- [ ] Экраны работают на 360px, 768px, 1280px+.
- [ ] Empty/error/loading/partial/stale/overdue состояния реализованы.
- [ ] Русский интерфейс и `ru-RU` форматы.
- [ ] Нет `parseFloat`/клиентских денежных расчётов.
- [ ] `is_stale`, `price_source`, `is_partial` отображаются по правилам handoff.
- [ ] Ошибки `409/400/422/502` обработаны.
- [ ] Скачивание JSON/CSV работает, filename из `Content-Disposition`.
- [ ] Production: `start.ps1`, FastAPI static + SPA fallback, deep links.
- [ ] README frontend и handoff актуальны.
- [ ] Финальное ревью PASS.

## 11. Риски и решения

| Риск | Влияние | Решение |
|---|---|---|
| PrimeNG 20.4.0 — MIT-линия (19–21) | Обновление на 22+ требует коммерческой лицензии; `@primeuix/themes` 3.x — тоже коммерческая | Пин `20.4.0` и `@primeuix/themes` `2.0.0` (MIT); апгрейд на 22+/themes 3.x — отдельное решение с юридической проверкой, вне MVP |
| Устаревшая линия Angular (security advisories) | Известные уязвимости в старом стеке | Scaffold пересобран на Angular 20.3.34 / CLI/build 20.3.42 — текущей поддерживаемой линии; версии запинены, `npm audit` — 0 vulnerabilities |
| Aura 16px base | Верстка, рассчитанная на 14px, поедет | Проверить на Stage 0; при необходимости свои токены |
| Версия Node локально vs CI | Расхождение окружений | Angular 20 официально поддерживает Node 20.19+/22.12+/24.x; локально проверено (Node 24.22 + Angular 20.3.34), версию фиксировать в `.nvmrc`/README |
| Деньги строками | Случайный `parseFloat` и ошибки округления | Запрет арифметики; форматтеры; code review; тесты |
| Клиентские расчёты | Расхождение с backend | Все суммы/доли/купоны — только из API |
| CORS/proxy | 403/network в dev | Proxy `/api`; CORS уже настроен; prod same origin |
| Объём графика | 365+ точек/год, ALL — больше | Chart.js decimation/`spanGaps`, не агрегировать деньги; проверить 1Y/ALL |
| MOEX недоступен | Поиск/добавление/refresh падают | Seed для demo; 502 handling; retry вручную |
| Долгий refresh | UI «зависает» | Loading, disable, 409, не запускать параллельно |
| Нет pagination | Большие списки | Для MVP объёмы малы; quote history ограничить периодом |
| Master-switch не виден в GET | Пользователь не понимает 400 | Объяснение в UI; revert switch; help text |
| Backend static serving | Можно сломать `/api`/`/docs` | Монтировать после API; smoke на все пути |
| Часовые пояса | Даты сдвигаются | Даты `YYYY-MM-DD` не парсить в Date; timestamps форматировать с TZ |

### 11.1. Принятые решения

- [ ] Angular 20.3.34 (CLI/build 20.3.42) standalone + signals; TypeScript 5.9.3, RxJS 7.8.2, Zone.js 0.15.1; без NgRx.
- [ ] PrimeNG 20.4.0 (MIT) + `@primeuix/themes` 2.0.0 (MIT), Aura light; license key не требуется (22+/themes 3.x — коммерческие, вне MVP).
- [ ] Chart.js 4.4.9 через PrimeNG `p-chart`, изолированно.
- [ ] Деньги/цены — строки; форматирование `Intl.NumberFormat('ru-RU')`.
- [ ] Периоды — server-side query; клиент не фильтрует series.
- [ ] Ошибки — единый `ApiError`; тосты для действий, inline для загрузки.
- [ ] Production — FastAPI same origin, SPA fallback, `start.ps1`.

## 12. Журнал изменений и ревью

### 12.1. Changelog

| Дата | Этап | Изменение | Автор |
|---|---|---|---|
| 2026-10-30 | — | Создан план (первоначальная версия стека) | — |
| 2026-10-30 | — | API сверен с OpenAPI и temp seeded-ответами | — |
| 2026-10-30 | — | Стек скорректирован и верифицирован: Angular **20.3.34** (CLI/build **20.3.42**), PrimeNG **20.4.0** (MIT) + `@primeuix/themes` **2.0.0** (MIT, Aura), PrimeIcons 7.0.0, Chart.js 4.4.9, TypeScript 5.9.3, RxJS 7.8.2, Zone.js 0.15.1, builder `@angular/build:application`, Karma + Jasmine (`@angular/build:karma`), Node 24.22; `npm audit` — 0 vulnerabilities. Заменяет все прежние записи о стеке | — |
| 2026-10-30 | 0 | Этап 0 завершён и прошёл независимое ревью (**PASS**): Angular 20.3.34 + PrimeNG 20.4.0 (MIT) shell, тема, routing, proxy, API/error/formatting foundation; 70 Karma-тестов, `npm run build`, `npm audit --omit=dev` — 0 vulnerabilities | — |
| 2026-11-01 | 1 | Этап 1 завершён и прошёл ревью (**PASS после исправлений**): сервисы Dashboard/Positions/Portfolio/Settings, дашборд с 5 карточками, графиком, позициями и купонами; runtime guard периода, исправлены высота/подписи графика; 95 Karma-тестов, `npm run build`, живая проверка seeded API и 360/1280 px | — |

### 12.2. Результаты ревью

Заполняется после каждого stage review.

| Этап | Дата | Вердикт | Находки | Статус |
|---|---|---|---|---|
| 0 | 2026-10-30 | PASS | 0 Critical / 0 Required; R1–R5 исправлены; визуальные pixel-check и a11y-аудит отложены до Stage 5 | [x] |
| 1 | 2026-11-01 | PASS после исправлений | 0 Critical; R1–R5 исправлены (guard периода, мёртвый код, англоязычный бейдж, интерполяция/высота/подписи графика); добавлены тесты late response и unknown period | [x] |
| 2 | — | — | — | [ ] |
| 3 | — | — | — | [ ] |
| 4 | — | — | — | [ ] |
| 5 | — | — | — | [ ] |
| 6 | — | — | — | [ ] |

### 12.3. Шаблон записи ревью

```text
Этап:
Дата:
Ревьюер:
Вердикт: PASS / PASS WITH FIXES / FAIL

Critical:
- ...

Required:
- ...

Optional:
- ...

Отложено осознанно:
- ...

Проверки:
- npm run build: ...
- npm test -- --watch=false --browsers=ChromeHeadless: ...
- ручной E2E: ...
```

---

**Итог:** после выполнения этапов 0–6 приложение должно запускаться одной командой, работать на seeded-данных без сети, корректно обрабатывать ошибки API и отдавать production-сборку через FastAPI.
