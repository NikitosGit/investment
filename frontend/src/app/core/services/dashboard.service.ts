import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiClient } from '../api/api-client.service';
import type { DashboardResponse, Period } from '../api/models';

/** Typed access to the dashboard endpoint. */
@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly api = inject(ApiClient);

  /**
   * Load dashboard totals, positions, the value series and upcoming coupons.
   *
   * When `period` is omitted the request carries no `period` query parameter,
   * so the backend applies the stored `dashboard_period` preference.
   */
  getDashboard(period?: Period): Observable<DashboardResponse> {
    return this.api.get<DashboardResponse>('/dashboard', period ? { period } : undefined);
  }
}
