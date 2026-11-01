import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiClient } from '../api/api-client.service';
import type { PositionListResponse } from '../api/models';
import { PositionsService } from './positions.service';

const POSITIONS: PositionListResponse = {
  items: [],
  total_market_value: '16242.00',
  total_invested: '15918.45',
};

describe('PositionsService', () => {
  let service: PositionsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ApiClient],
    });

    service = TestBed.inject(PositionsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads open positions from GET /api/positions', () => {
    let result: PositionListResponse | undefined;
    service.getPositions().subscribe((response) => (result = response));

    const request = http.expectOne('/api/positions');
    expect(request.request.method).toBe('GET');
    request.flush(POSITIONS);

    expect(result).toEqual(POSITIONS);
    expect(result?.total_market_value).toBe('16242.00');
  });
});
