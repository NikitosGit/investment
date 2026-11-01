import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiClient } from '../api/api-client.service';
import type { OperationListResponse, OperationResponse } from '../api/models';
import { OperationsService } from './operations.service';

const OPERATION: OperationResponse = {
  id: 5,
  asset_id: 2,
  type: 'BUY',
  trade_date: '2026-10-29',
  quantity: 1,
  input_price: '97.600000',
  input_price_type: 'PERCENT',
  price_rub: '780.800000',
  note: 'Докупка ОФЗ',
};

describe('OperationsService', () => {
  let service: OperationsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ApiClient],
    });

    service = TestBed.inject(OperationsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists operations with asset and date filters', () => {
    let result: OperationListResponse | undefined;
    service
      .list({ assetId: 2, from: '2026-01-01', to: '2026-12-31' })
      .subscribe((response) => (result = response));

    const request = http.expectOne(
      (candidate) =>
        candidate.url === '/api/operations' &&
        candidate.params.get('asset_id') === '2' &&
        candidate.params.get('from') === '2026-01-01' &&
        candidate.params.get('to') === '2026-12-31',
    );
    expect(request.request.method).toBe('GET');
    request.flush({ items: [] });

    expect(result?.items).toEqual([]);
  });

  it('creates a bond operation with a PERCENT price kept as a string', () => {
    let result: OperationResponse | undefined;
    service
      .create({
        asset_id: 2,
        type: 'BUY',
        trade_date: '2026-10-29',
        quantity: 1,
        price: '97.600',
        price_type: 'PERCENT',
        note: 'Докупка ОФЗ',
      })
      .subscribe((response) => (result = response));

    const request = http.expectOne('/api/operations');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.price).toBe('97.600');
    expect(request.request.body.price_type).toBe('PERCENT');
    request.flush(OPERATION);

    expect(result?.price_rub).toBe('780.800000');
  });

  it('patches only the provided fields and deletes', () => {
    service.update(5, { quantity: 6 }).subscribe();
    const patch = http.expectOne('/api/operations/5');
    expect(patch.request.method).toBe('PATCH');
    expect(patch.request.body).toEqual({ quantity: 6 });
    patch.flush({ ...OPERATION, quantity: 6 });

    service.remove(5).subscribe();
    const remove = http.expectOne('/api/operations/5');
    expect(remove.request.method).toBe('DELETE');
    remove.flush(null, { status: 204, statusText: 'No Content' });
  });
});
