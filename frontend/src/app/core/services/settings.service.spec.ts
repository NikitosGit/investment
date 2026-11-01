import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiClient } from '../api/api-client.service';
import type { SettingsResponse } from '../api/models';
import { SettingsService } from './settings.service';

const SETTINGS: SettingsResponse = {
  quote_refresh_enabled: false,
  dashboard_period: '1Y',
};

describe('SettingsService', () => {
  let service: SettingsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ApiClient],
    });

    service = TestBed.inject(SettingsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads settings from GET /api/settings', () => {
    let result: SettingsResponse | undefined;
    service.getSettings().subscribe((response) => (result = response));

    const request = http.expectOne('/api/settings');
    expect(request.request.method).toBe('GET');
    request.flush(SETTINGS);

    expect(result).toEqual(SETTINGS);
    expect(result?.dashboard_period).toBe('1Y');
  });

  it('patches settings with only the provided fields', () => {
    let result: SettingsResponse | undefined;
    service.updateSettings({ dashboard_period: '3M' }).subscribe((response) => (result = response));

    const request = http.expectOne('/api/settings');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ dashboard_period: '3M' });
    request.flush({ ...SETTINGS, dashboard_period: '3M' });

    expect(result?.dashboard_period).toBe('3M');
  });
});
