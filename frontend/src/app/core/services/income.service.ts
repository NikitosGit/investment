import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiClient, type QueryParams } from '../api/api-client.service';
import type {
  IncomeCreateIn,
  IncomeItem,
  IncomeKind,
  IncomeListResponse,
  IncomeStatus,
  IncomeUpdateIn,
  MarkPaidIn,
} from '../api/models';

/** Optional filters for the income list. */
export interface IncomeFilters {
  status?: IncomeStatus;
  kind?: IncomeKind;
  assetId?: number;
  /** Inclusive ISO date (`YYYY-MM-DD`). */
  from?: string;
  /** Inclusive ISO date (`YYYY-MM-DD`). */
  to?: string;
}

/** Typed access to dividends, coupons and their confirmation flow. */
@Injectable({ providedIn: 'root' })
export class IncomeService {
  private readonly api = inject(ApiClient);

  list(filters: IncomeFilters = {}): Observable<IncomeListResponse> {
    const params: QueryParams = {
      status: filters.status,
      kind: filters.kind,
      asset_id: filters.assetId,
      from: filters.from,
      to: filters.to,
    };
    return this.api.get<IncomeListResponse>('/income', params);
  }

  create(payload: IncomeCreateIn): Observable<IncomeItem> {
    return this.api.post<IncomeItem, IncomeCreateIn>('/income', payload);
  }

  update(incomeId: number, payload: IncomeUpdateIn): Observable<IncomeItem> {
    return this.api.patch<IncomeItem>(`/income/${incomeId}`, payload);
  }

  markPaid(incomeId: number, payload: MarkPaidIn = {}): Observable<IncomeItem> {
    return this.api.post<IncomeItem, MarkPaidIn>(`/income/${incomeId}/mark-paid`, payload);
  }

  remove(incomeId: number): Observable<void> {
    return this.api.delete(`/income/${incomeId}`);
  }
}
