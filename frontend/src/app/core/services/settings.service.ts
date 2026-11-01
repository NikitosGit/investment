import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiClient } from '../api/api-client.service';
import type { SettingsResponse, SettingsUpdate } from '../api/models';

/** Typed access to the effective application settings. */
@Injectable({ providedIn: 'root' })
export class SettingsService {
  private readonly api = inject(ApiClient);

  getSettings(): Observable<SettingsResponse> {
    return this.api.get<SettingsResponse>('/settings');
  }

  updateSettings(payload: SettingsUpdate): Observable<SettingsResponse> {
    return this.api.patch<SettingsResponse>('/settings', payload);
  }
}
