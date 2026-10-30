import { Routes } from '@angular/router';

import { ShellComponent } from './layout/shell/shell.component';

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
        path: 'assets/:assetId',
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
