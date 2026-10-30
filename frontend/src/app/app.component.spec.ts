import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { Router, provideRouter } from '@angular/router';
import Aura from '@primeuix/themes/aura';
import { ConfirmationService, MessageService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';

import type { HealthResponse } from './core/api/models';
import { apiErrorInterceptor } from './core/interceptors/api-error.interceptor';
import { AppComponent } from './app.component';
import { routes } from './app.routes';

const HEALTH: HealthResponse = {
  status: 'ok',
  version: '0.1.0',
  database: 'ok',
  moex: 'unknown',
  last_quote_refresh_at: null,
};

describe('AppComponent', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideRouter(routes),
        provideHttpClient(withInterceptors([apiErrorInterceptor])),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
        MessageService,
        ConfirmationService,
      ],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('creates the app and renders the router outlet', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();

    expect(fixture.componentInstance).toBeTruthy();
    expect(fixture.debugElement.query(By.css('router-outlet'))).toBeTruthy();
  });

  it('navigates to the dashboard and loads health through the real routes', async () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();

    await TestBed.inject(Router).navigateByUrl('/dashboard');
    fixture.detectChanges();

    const request = http.expectOne((req) => req.url === '/api/health');
    expect(request.request.method).toBe('GET');
    request.flush(HEALTH);

    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('app-shell')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('h1')?.textContent).toContain('Дашборд');
  });
});
