import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiClient } from '../api/api-client.service';
import type { PortfolioResponse } from '../api/models';

/** Typed access to the single local portfolio. */
@Injectable({ providedIn: 'root' })
export class PortfolioService {
  private readonly api = inject(ApiClient);

  getPortfolio(): Observable<PortfolioResponse> {
    return this.api.get<PortfolioResponse>('/portfolio');
  }
}
