import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter, NavigationStart, Router } from '@angular/router';
import Aura from '@primeuix/themes/aura';
import { ConfirmationService, MessageService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';
import { of, throwError } from 'rxjs';

import { ApiError } from '../../core/api/api-error';
import type { HealthResponse } from '../../core/api/models';
import { HealthService } from '../../core/services/health.service';
import { ShellComponent } from './shell.component';

const HEALTH: HealthResponse = {
  status: 'ok',
  version: '0.1.0',
  database: 'ok',
  moex: 'unknown',
  last_quote_refresh_at: null,
};

describe('ShellComponent', () => {
  let health: jasmine.SpyObj<HealthService>;

  beforeEach(async () => {
    health = jasmine.createSpyObj<HealthService>('HealthService', ['get']);
    health.get.and.returnValue(of(HEALTH));

    await TestBed.configureTestingModule({
      imports: [ShellComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
        MessageService,
        ConfirmationService,
        { provide: HealthService, useValue: health },
      ],
    }).compileComponents();
  });

  it('renders the sidebar navigation and a router outlet', () => {
    const fixture = TestBed.createComponent(ShellComponent);
    fixture.detectChanges();

    const links = fixture.debugElement
      .queryAll(By.css('app-sidebar a'))
      .map((element) => (element.nativeElement as HTMLElement).textContent?.trim());

    expect(links).toEqual(['Дашборд', 'Портфель', 'Доходы', 'Настройки']);
    expect(fixture.debugElement.query(By.css('router-outlet'))).toBeTruthy();
  });

  it('shows the API health badge and requests health once', () => {
    const fixture = TestBed.createComponent(ShellComponent);
    fixture.detectChanges();

    const badge = fixture.debugElement.query(By.css('.shell__health')).nativeElement as HTMLElement;

    expect(badge.textContent).toContain('Сервер: работает');
    expect(health.get).toHaveBeenCalledTimes(1);
  });

  it('keeps the shell usable when health check fails', () => {
    health.get.and.returnValue(
      throwError(() => new ApiError(0, 'NETWORK_ERROR', 'Нет связи с сервером')),
    );

    const fixture = TestBed.createComponent(ShellComponent);
    fixture.detectChanges();

    expect(fixture.componentInstance.healthState()).toBe('offline');
    const badge = fixture.debugElement.query(By.css('.shell__health')).nativeElement as HTMLElement;
    expect(badge.textContent).toContain('Сервер: недоступен');
  });

  it('does not show a hardcoded version when health is unavailable', () => {
    health.get.and.returnValue(
      throwError(() => new ApiError(0, 'NETWORK_ERROR', 'Нет связи с сервером')),
    );

    const fixture = TestBed.createComponent(ShellComponent);
    fixture.detectChanges();

    const footer = fixture.debugElement.query(By.css('.shell__footer')).nativeElement as HTMLElement;
    expect(footer.textContent).not.toContain('v0.1.0');
  });

  it('toggles the mobile menu and closes it on Escape', () => {
    const fixture = TestBed.createComponent(ShellComponent);
    fixture.detectChanges();

    const button = fixture.debugElement.query(By.css('.shell__menu-button'))
      .nativeElement as HTMLButtonElement;

    expect(button.getAttribute('aria-expanded')).toBe('false');
    expect(button.getAttribute('aria-controls')).toBeNull();
    expect(fixture.debugElement.query(By.css('#mobile-menu'))).toBeNull();

    button.click();
    fixture.detectChanges();

    expect(fixture.componentInstance.menuOpen()).toBeTrue();
    expect(button.getAttribute('aria-expanded')).toBe('true');
    expect(button.getAttribute('aria-controls')).toBe('mobile-menu');
    expect(fixture.debugElement.query(By.css('#mobile-menu'))).toBeTruthy();

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    fixture.detectChanges();

    expect(fixture.componentInstance.menuOpen()).toBeFalse();
    expect(button.getAttribute('aria-controls')).toBeNull();
    expect(fixture.debugElement.query(By.css('#mobile-menu'))).toBeNull();
  });

  it('focuses main when the mobile menu closes for navigation', () => {
    const fixture = TestBed.createComponent(ShellComponent);
    fixture.detectChanges();

    const main = fixture.debugElement.query(By.css('main')).nativeElement as HTMLElement;
    fixture.componentInstance.menuOpen.set(true);
    fixture.componentInstance.closeMenu('main');

    expect(document.activeElement).toBe(main);
  });

  it('returns focus to the menu button after Escape closes the mobile menu', () => {
    const fixture = TestBed.createComponent(ShellComponent);
    fixture.detectChanges();

    const button = fixture.debugElement.query(By.css('.shell__menu-button'))
      .nativeElement as HTMLButtonElement;
    button.click();
    fixture.detectChanges();

    const link = fixture.debugElement.query(By.css('#mobile-menu a'))
      .nativeElement as HTMLAnchorElement;
    link.focus();
    expect(document.activeElement).toBe(link);

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    fixture.detectChanges();

    expect(document.activeElement).toBe(button);
  });

  it('provides a skip link that focuses main without navigating', () => {
    const fixture = TestBed.createComponent(ShellComponent);
    fixture.detectChanges();

    const router = TestBed.inject(Router);
    let navigationStarts = 0;
    const subscription = router.events.subscribe((event) => {
      if (event instanceof NavigationStart) {
        navigationStarts += 1;
      }
    });

    const skipLink = fixture.debugElement.query(By.css('.skip-link'))
      .nativeElement as HTMLAnchorElement;
    const main = fixture.debugElement.query(By.css('main'))
      .nativeElement as HTMLElement;
    const urlBefore = router.url;
    const hrefBefore = window.location.href;

    skipLink.click();
    fixture.detectChanges();

    expect(document.activeElement).toBe(main);
    expect(router.url).toBe(urlBefore);
    expect(window.location.href).toBe(hrefBefore);
    expect(navigationStarts).toBe(0);
    subscription.unsubscribe();

    expect(skipLink.getAttribute('href')).toBe('#main-content');
    expect(main.id).toBe('main-content');
    expect(main.getAttribute('aria-label')).toBe('Основное содержимое');
    expect(main.getAttribute('tabindex')).toBe('-1');
  });

  it('returns focus to the trigger after a confirmation closes', () => {
    const fixture = TestBed.createComponent(ShellComponent);
    fixture.detectChanges();

    const trigger = document.createElement('button');
    const other = document.createElement('button');
    document.body.append(trigger, other);
    trigger.focus();

    TestBed.inject(ConfirmationService).confirm({ message: 'Удалить операцию?' });
    other.focus();
    fixture.componentInstance.onConfirmHide();

    expect(document.activeElement).toBe(trigger);
    trigger.remove();
    other.remove();
  });
});
