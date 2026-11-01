import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiClient, type QueryParams } from '../api/api-client.service';
import type {
  OperationCreateIn,
  OperationListResponse,
  OperationResponse,
  OperationUpdateIn,
} from '../api/models';

/** Optional filters for the operation list. */
export interface OperationFilters {
  assetId?: number;
  /** Inclusive ISO date (`YYYY-MM-DD`). */
  from?: string;
  /** Inclusive ISO date (`YYYY-MM-DD`). */
  to?: string;
}

/** Typed access to buy/sell operations. */
@Injectable({ providedIn: 'root' })
export class OperationsService {
  private readonly api = inject(ApiClient);

  list(filters: OperationFilters = {}): Observable<OperationListResponse> {
    const params: QueryParams = {
      asset_id: filters.assetId,
      from: filters.from,
      to: filters.to,
    };
    return this.api.get<OperationListResponse>('/operations', params);
  }

  create(payload: OperationCreateIn): Observable<OperationResponse> {
    return this.api.post<OperationResponse, OperationCreateIn>('/operations', payload);
  }

  update(operationId: number, payload: OperationUpdateIn): Observable<OperationResponse> {
    return this.api.patch<OperationResponse>(`/operations/${operationId}`, payload);
  }

  remove(operationId: number): Observable<void> {
    return this.api.delete(`/operations/${operationId}`);
  }
}
