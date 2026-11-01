import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiClient } from '../api/api-client.service';
import { QuotesService } from './quotes.service';

describe('QuotesService', () => {
  let service: QuotesService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ApiClient],
    });

    service = TestBed.inject(QuotesService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads price history with the requested period', () => {
    service.history(2, '3M').subscribe();

    const request = http.expectOne(
      (candidate) =>
        candidate.url === '/api/quotes/2/history' && candidate.params.get('period') === '3M',
    );
    expect(request.request.method).toBe('GET');
    request.flush({ asset_id: 2, period: '3M', items: [] });
  });

  it('defaults the history period to 1Y', () => {
    service.history(1).subscribe();

    const request = http.expectOne(
      (candidate) => candidate.url === '/api/quotes/1/history' && candidate.params.get('period') === '1Y',
    );
    request.flush({ asset_id: 1, period: '1Y', items: [] });
  });

  it('refreshes every asset and stores a manual quote', () => {
    service.refreshAll().subscribe();
    const refresh = http.expectOne('/api/quotes/refresh');
    expect(refresh.request.method).toBe('POST');
    refresh.flush({ updated: 2, failed: 0, last_refresh_at: '2026-10-30T16:05:00', errors: [] });

    service
      .addManual({
        asset_id: 1,
        quote_date: '2026-10-30',
        price: '302.00',
        price_type: 'RUB',
      })
      .subscribe();
    const manual = http.expectOne('/api/quotes/manual');
    expect(manual.request.method).toBe('POST');
    expect(manual.request.body.price).toBe('302.00');
    manual.flush({
      id: 1,
      asset_id: 1,
      quote_date: '2026-10-30',
      price: '302.000000',
      price_type: 'RUB',
      source: 'MANUAL',
      fetched_at: '2026-10-30T16:05:00Z',
    });
  });
});
