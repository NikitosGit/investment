import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import Aura from '@primeuix/themes/aura';
import { ConfirmationService, MessageService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';
import { of } from 'rxjs';

import type { DashboardResponse, HealthResponse } from '../../core/api/models';
import { DashboardService } from '../../core/services/dashboard.service';
import { HealthService } from '../../core/services/health.service';
import { routes } from '../../app.routes';

const HEALTH: HealthResponse = {
  status: 'ok',
  version: '0.1.0',
  database: 'ok',
  moex: 'unknown',
  last_quote_refresh_at: null,
};

const DASHBOARD: DashboardResponse = {
  as_of: '2026-10-30',
  currency: 'RUB',
  period: '1Y',
  totals: {
    market_value: '0.00',
    invested: '0.00',
    dividends_paid: '0.00',
    coupons_paid: '0.00',
    income_paid_total: '0.00',
    expected_coupons: '0.00',
    positions_count: 0,
    assets_count: 0,
  },
  series: [],
  positions: [],
  upcoming_coupons: [],
  is_partial: false,
};

describe('ShellComponent routing', () => {
  let harness: RouterTestingHarness;

  beforeEach(async () => {
    const health = jasmine.createSpyObj<HealthService>('HealthService', ['get']);
    health.get.and.returnValue(of(HEALTH));

    const dashboard = jasmine.createSpyObj<DashboardService>('DashboardService', [
      'getDashboard',
    ]);
    dashboard.getDashboard.and.returnValue(of(DASHBOARD));

    await TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
        MessageService,
        ConfirmationService,
        { provide: HealthService, useValue: health },
        { provide: DashboardService, useValue: dashboard },
      ],
    }).compileComponents();

    harness = await RouterTestingHarness.create('/dashboard');
  });

  function portfolioLink(): HTMLAnchorElement {
    const link = harness.fixture.nativeElement.querySelector(
      'a[data-section="portfolio"]',
    ) as HTMLAnchorElement | null;

    if (!link) {
      throw new Error('Portfolio navigation link was not rendered');
    }

    return link;
  }

  it('marks portfolio active on an asset card and keeps it after navigating to portfolio', async () => {
    await harness.navigateByUrl('/assets/1');
    harness.detectChanges();

    expect(portfolioLink().classList).toContain('is-active');
    expect(portfolioLink().getAttribute('aria-current')).toBe('page');

    await harness.navigateByUrl('/portfolio');
    harness.detectChanges();

    expect(portfolioLink().classList).toContain('is-active');
    expect(portfolioLink().getAttribute('aria-current')).toBe('page');
  });

  it('marks the dashboard section active', async () => {
    await harness.navigateByUrl('/dashboard');
    harness.detectChanges();

    const dashboard = harness.fixture.nativeElement.querySelector(
      'a[data-section="dashboard"]',
    ) as HTMLAnchorElement;

    expect(dashboard.classList).toContain('is-active');
    expect(dashboard.getAttribute('aria-current')).toBe('page');
    expect(portfolioLink().classList).not.toContain('is-active');
  });
});
