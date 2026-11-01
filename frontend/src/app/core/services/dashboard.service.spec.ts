import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiClient } from '../api/api-client.service';
import type { DashboardResponse } from '../api/models';
import { DashboardService } from './dashboard.service';

const DASHBOARD: DashboardResponse = {
  as_of: '2026-10-30',
  currency: 'RUB',
  period: '1Y',
  totals: {
    market_value: '16242.00',
    invested: '15918.45',
    dividends_paid: '200.00',
    coupons_paid: '525.00',
    income_paid_total: '725.00',
    expected_coupons: '1575.00',
    positions_count: 0,
    assets_count: 0,
  },
  series: [
    { date: '2026-10-30', market_value: '16242.00', invested: '15918.45', is_partial: true },
  ],
  positions: [],
  upcoming_coupons: [],
  is_partial: true,
};

describe('DashboardService', () => {
  let service: DashboardService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ApiClient],
    });

    service = TestBed.inject(DashboardService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads the dashboard without a period query parameter by default', () => {
    let result: DashboardResponse | undefined;
    service.getDashboard().subscribe((response) => (result = response));

    const request = http.expectOne('/api/dashboard');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.has('period')).toBeFalse();
    request.flush(DASHBOARD);

    expect(result).toEqual(DASHBOARD);
  });

  it('sends an explicit period', () => {
    service.getDashboard('3M').subscribe();

    const request = http.expectOne(
      (candidate) =>
        candidate.url === '/api/dashboard' && candidate.params.get('period') === '3M',
    );
    expect(request.request.method).toBe('GET');
    request.flush({ ...DASHBOARD, period: '3M' });
  });

  it('preserves string money values and the partial flag', () => {
    let result: DashboardResponse | undefined;
    service.getDashboard().subscribe((response) => (result = response));

    http.expectOne('/api/dashboard').flush(DASHBOARD);

    expect(result?.totals.market_value).toBe('16242.00');
    expect(result?.series[0].market_value).toBe('16242.00');
    expect(result?.is_partial).toBeTrue();
  });
});
