import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiClient } from '../api/api-client.service';
import type { PortfolioResponse } from '../api/models';
import { PortfolioService } from './portfolio.service';

const PORTFOLIO: PortfolioResponse = {
  id: 1,
  name: 'Мой портфель',
  base_currency: 'RUB',
  created_at: '2026-10-30T15:10:12.092327Z',
};

describe('PortfolioService', () => {
  let service: PortfolioService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ApiClient],
    });

    service = TestBed.inject(PortfolioService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads the portfolio from GET /api/portfolio', () => {
    let result: PortfolioResponse | undefined;
    service.getPortfolio().subscribe((response) => (result = response));

    const request = http.expectOne('/api/portfolio');
    expect(request.request.method).toBe('GET');
    request.flush(PORTFOLIO);

    expect(result).toEqual(PORTFOLIO);
    expect(result?.base_currency).toBe('RUB');
  });
});
