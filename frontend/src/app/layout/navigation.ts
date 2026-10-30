/** Top-level navigation sections. */
export type NavSection = 'dashboard' | 'portfolio' | 'income' | 'settings';

export interface NavItem {
  path: string;
  label: string;
  icon: string;
  section: NavSection;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { path: '/dashboard', label: 'Дашборд', icon: 'pi pi-chart-line', section: 'dashboard' },
  { path: '/portfolio', label: 'Портфель', icon: 'pi pi-briefcase', section: 'portfolio' },
  { path: '/income', label: 'Доходы', icon: 'pi pi-wallet', section: 'income' },
  { path: '/settings', label: 'Настройки', icon: 'pi pi-cog', section: 'settings' },
];

/**
 * Map a router URL to the navigation section that should be highlighted.
 *
 * Asset cards live under `/assets/:assetId` but belong to the portfolio
 * section, so both `/portfolio` and `/assets/...` map to `portfolio`.
 */
export function activeSectionForUrl(url: string): NavSection | null {
  const path = url.split(/[?#]/)[0] || '/';

  if (path === '/' || path.length === 0) {
    return null;
  }

  if (path === '/dashboard' || path.startsWith('/dashboard/')) {
    return 'dashboard';
  }

  if (
    path === '/portfolio' ||
    path.startsWith('/portfolio/') ||
    path === '/assets' ||
    path.startsWith('/assets/')
  ) {
    return 'portfolio';
  }

  if (path === '/income' || path.startsWith('/income/')) {
    return 'income';
  }

  if (path === '/settings' || path.startsWith('/settings/')) {
    return 'settings';
  }

  return null;
}
