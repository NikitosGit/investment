import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiClient } from '../api/api-client.service';
import type { IncomeItem, IncomeListResponse } from '../api/models';
import { IncomeService } from './income.service';

const INCOME: IncomeItem = {
  id: 3,
  asset_id: 2,
  asset_secid: 'SU26238RMFS4',
  kind: 'COUPON',
  status: 'EXPECTED',
  amount_per_unit: '35.00',
  quantity: 15,
  amount_total: '525.00',
  currency: 'RUB',
  record_date: null,
  pay_date: '2026-11-09',
  source: 'MANUAL',
  note: null,
  is_overdue: false,
};

const EMPTY_TOTALS = {
  dividends_paid: '0.00',
  coupons_paid: '0.00',
  expected_coupons: '0.00',
};

describe('IncomeService', () => {
  let service: IncomeService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ApiClient],
    });

    service = TestBed.inject(IncomeService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists income with every supported filter', () => {
    let result: IncomeListResponse | undefined;
    service
      .list({
        status: 'PAID',
        kind: 'COUPON',
        assetId: 2,
        from: '2026-01-01',
        to: '2026-12-31',
      })
      .subscribe((response) => (result = response));

    const request = http.expectOne(
      (candidate) =>
        candidate.url === '/api/income' &&
        candidate.params.get('status') === 'PAID' &&
        candidate.params.get('kind') === 'COUPON' &&
        candidate.params.get('asset_id') === '2' &&
        candidate.params.get('from') === '2026-01-01' &&
        candidate.params.get('to') === '2026-12-31',
    );
    expect(request.request.method).toBe('GET');
    request.flush({ items: [], totals: EMPTY_TOTALS });

    expect(result?.items).toEqual([]);
  });

  it('creates a manual income and confirms an expected coupon', () => {
    service
      .create({
        asset_id: 1,
        kind: 'DIVIDEND',
        amount_total: '150.00',
        pay_date: '2026-10-30',
        note: null,
      })
      .subscribe();
    const create = http.expectOne('/api/income');
    expect(create.request.method).toBe('POST');
    expect(create.request.body.amount_total).toBe('150.00');
    create.flush({ ...INCOME, kind: 'DIVIDEND', status: 'PAID' });

    service.markPaid(3, { amount_total: '525.00' }).subscribe();
    const markPaid = http.expectOne('/api/income/3/mark-paid');
    expect(markPaid.request.method).toBe('POST');
    expect(markPaid.request.body).toEqual({ amount_total: '525.00' });
    markPaid.flush({ ...INCOME, status: 'PAID' });
  });

  it('patches only changed fields and deletes', () => {
    service.update(3, { note: 'Уточнено' }).subscribe();
    const patch = http.expectOne('/api/income/3');
    expect(patch.request.method).toBe('PATCH');
    expect(patch.request.body).toEqual({ note: 'Уточнено' });
    patch.flush({ ...INCOME, note: 'Уточнено' });

    service.remove(3).subscribe();
    const remove = http.expectOne('/api/income/3');
    expect(remove.request.method).toBe('DELETE');
    remove.flush(null, { status: 204, statusText: 'No Content' });
  });
});
