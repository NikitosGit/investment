import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiClient } from '../api/api-client.service';
import type { HealthResponse } from '../api/models';

/** Typed access to the service health endpoint. */
@Injectable({ providedIn: 'root' })
export class HealthService {
  private readonly api = inject(ApiClient);

  get(): Observable<HealthResponse> {
    return this.api.get<HealthResponse>('/health');
  }
}
