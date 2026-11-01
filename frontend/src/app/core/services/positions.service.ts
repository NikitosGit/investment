import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiClient } from '../api/api-client.service';
import type { PositionListResponse } from '../api/models';

/** Typed access to the open positions endpoint. */
@Injectable({ providedIn: 'root' })
export class PositionsService {
  private readonly api = inject(ApiClient);

  getPositions(): Observable<PositionListResponse> {
    return this.api.get<PositionListResponse>('/positions');
  }
}
