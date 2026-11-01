import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiClient } from '../api/api-client.service';
import type {
  ManualQuoteIn,
  QuoteHistoryResponse,
  QuoteItem,
  QuotePeriod,
  QuoteRefreshResponse,
} from '../api/models';

/** Typed access to cached quotes, history and refreshes. */
@Injectable({ providedIn: 'root' })
export class QuotesService {
  private readonly api = inject(ApiClient);

  history(assetId: number, period: QuotePeriod = '1Y'): Observable<QuoteHistoryResponse> {
    return this.api.get<QuoteHistoryResponse>(`/quotes/${assetId}/history`, { period });
  }

  refreshAll(): Observable<QuoteRefreshResponse> {
    return this.api.post<QuoteRefreshResponse>('/quotes/refresh');
  }

  addManual(payload: ManualQuoteIn): Observable<QuoteItem> {
    return this.api.post<QuoteItem, ManualQuoteIn>('/quotes/manual', payload);
  }
}
