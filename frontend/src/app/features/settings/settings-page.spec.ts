import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import Aura from '@primeuix/themes/aura';
import { MessageService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';
import { Subject, of, throwError } from 'rxjs';

import { ApiError } from '../../core/api/api-error';
import type {
  BackupResponse,
  HealthResponse,
  QuoteRefreshResponse,
  SettingsResponse,
} from '../../core/api/models';
import { DatePipe } from '../../core/formatting/date.pipe';
import { HealthService } from '../../core/services/health.service';
import { NotificationService } from '../../core/services/notification.service';
import { QuotesService } from '../../core/services/quotes.service';
import { SettingsService } from '../../core/services/settings.service';
import { SystemService } from '../../core/services/system.service';
import {
  SettingsPage,
  exportFallbackFilename,
  formatFileSize,
} from './settings-page';

const HEALTH: HealthResponse = {
  status: 'ok',
  version: '0.1.0',
  database: 'ok',
  moex: 'unknown',
  last_quote_refresh_at: null,
};

const SETTINGS: SettingsResponse = {
  quote_refresh_enabled: true,
  dashboard_period: '1Y',
};

const REFRESH_OK: QuoteRefreshResponse = {
  updated: 2,
  failed: 0,
  last_refresh_at: '2026-10-30T19:05:00+03:00',
  errors: [],
};

const REFRESH_PARTIAL: QuoteRefreshResponse = {
  updated: 1,
  failed: 1,
  last_refresh_at: '2026-10-30T19:05:00+03:00',
  errors: [{ asset_id: 1, secid: 'SBER', error: 'MOEX недоступен' }],
};

const BACKUP: BackupResponse = {
  path: 'data/backups/investments-20261030-181012.db',
  size_bytes: 106496,
  created_at: '2026-10-30T18:10:12.870080+03:00',
};

const NETWORK_ERROR = new ApiError(0, 'NETWORK_ERROR', 'Нет связи с backend');
const MASTER_SWITCH_ERROR = new ApiError(
  400,
  'BAD_REQUEST',
  'Автоматическое обновление котировок отключено настройками развёртывания',
);

function normalize(value: string): string {
  return value.replace(/[\u00a0\u202f]/g, ' ');
}

function textOf(element: HTMLElement): string {
  return normalize(element.textContent ?? '');
}

describe('SettingsPage', () => {
  let health: jasmine.SpyObj<HealthService>;
  let settingsService: jasmine.SpyObj<SettingsService>;
  let quotes: jasmine.SpyObj<QuotesService>;
  let system: jasmine.SpyObj<SystemService>;
  let notifications: jasmine.SpyObj<NotificationService>;

  beforeEach(async () => {
    health = jasmine.createSpyObj<HealthService>('HealthService', ['get']);
    health.get.and.returnValue(of(HEALTH));

    settingsService = jasmine.createSpyObj<SettingsService>('SettingsService', [
      'getSettings',
      'updateSettings',
    ]);
    settingsService.getSettings.and.returnValue(of(SETTINGS));
    settingsService.updateSettings.and.callFake((payload) =>
      of({ ...SETTINGS, ...payload } as SettingsResponse),
    );

    quotes = jasmine.createSpyObj<QuotesService>('QuotesService', ['refreshAll']);
    quotes.refreshAll.and.returnValue(of(REFRESH_OK));

    system = jasmine.createSpyObj<SystemService>('SystemService', [
      'createBackup',
      'export',
    ]);
    system.createBackup.and.returnValue(of(BACKUP));
    system.export.and.callFake((format) =>
      of({
        blob: new Blob([format]),
        filename:
          format === 'csv'
            ? 'investments-export-20261030-181012.zip'
            : 'investments-export-20261030-181012.json',
      }),
    );

    notifications = jasmine.createSpyObj<NotificationService>('NotificationService', [
      'success',
      'info',
      'warn',
      'error',
    ]);

    await TestBed.configureTestingModule({
      imports: [SettingsPage],
      providers: [
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
        MessageService,
        { provide: HealthService, useValue: health },
        { provide: SettingsService, useValue: settingsService },
        { provide: QuotesService, useValue: quotes },
        { provide: SystemService, useValue: system },
        { provide: NotificationService, useValue: notifications },
      ],
    }).compileComponents();
  });

  function create(): ComponentFixture<SettingsPage> {
    const fixture = TestBed.createComponent(SettingsPage);
    fixture.detectChanges();
    return fixture;
  }

  it('loads health and settings independently and renders their values', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;
    const content = textOf(element);

    expect(health.get).toHaveBeenCalledTimes(1);
    expect(settingsService.getSettings).toHaveBeenCalledTimes(1);

    expect(content).toContain('Работает');
    expect(content).toContain('0.1.0');
    expect(content).toContain('Доступна');
    expect(content).toContain('Не проверялся');
    expect(content).toContain('Ещё не обновлялось');
    expect(content).toContain('Автоматическое обновление котировок');
    expect(content).toContain('Период дашборда');
    expect(fixture.componentInstance.quoteRefreshEnabled()).toBeTrue();
    expect(fixture.componentInstance.dashboardPeriod()).toBe('1Y');
  });

  it('keeps settings usable when health fails and retries only health', () => {
    health.get.and.returnValue(throwError(() => NETWORK_ERROR));

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelectorAll('app-error-state').length).toBe(1);
    expect(textOf(element)).toContain('Нет связи с backend');
    expect(textOf(element)).toContain('Автоматическое обновление котировок');

    health.get.and.returnValue(of(HEALTH));
    element.querySelector<HTMLButtonElement>('app-error-state button')?.click();
    fixture.detectChanges();

    expect(health.get).toHaveBeenCalledTimes(2);
    expect(settingsService.getSettings).toHaveBeenCalledTimes(1);
    expect(textOf(element)).toContain('Работает');
    expect(element.querySelectorAll('app-error-state').length).toBe(0);
  });

  it('keeps health usable when settings fail and retries only settings', () => {
    settingsService.getSettings.and.returnValue(throwError(() => NETWORK_ERROR));

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    expect(textOf(element)).toContain('Работает');
    expect(element.querySelectorAll('app-error-state').length).toBe(1);
    expect(textOf(element)).not.toContain('Период дашборда');

    settingsService.getSettings.and.returnValue(of(SETTINGS));
    element.querySelector<HTMLButtonElement>('app-error-state button')?.click();
    fixture.detectChanges();

    expect(settingsService.getSettings).toHaveBeenCalledTimes(2);
    expect(health.get).toHaveBeenCalledTimes(1);
    expect(textOf(element)).toContain('Период дашборда');
  });

  it('patches only quote_refresh_enabled and applies the response', () => {
    const fixture = create();
    settingsService.updateSettings.and.returnValue(
      of({ ...SETTINGS, quote_refresh_enabled: false }),
    );

    fixture.componentInstance.onQuoteRefreshChange(false);
    fixture.detectChanges();

    expect(settingsService.updateSettings).toHaveBeenCalledOnceWith({
      quote_refresh_enabled: false,
    });
    expect(fixture.componentInstance.quoteRefreshEnabled()).toBeFalse();
    expect(notifications.success).toHaveBeenCalled();
    expect(notifications.error).not.toHaveBeenCalled();
  });

  it('reverts the toggle and explains the deployment master-switch on 400', () => {
    const fixture = create();
    settingsService.updateSettings.and.returnValue(
      throwError(() => MASTER_SWITCH_ERROR),
    );

    fixture.componentInstance.onQuoteRefreshChange(false);
    fixture.detectChanges();

    expect(fixture.componentInstance.quoteRefreshEnabled()).toBeTrue();
    expect(notifications.warn).toHaveBeenCalled();
    const [message, summary] = notifications.warn.calls.mostRecent().args;
    expect(message).toBe(
      'Автоматическое обновление отключено настройками развёртывания: включить его можно только на сервере. Ручное обновление котировок доступно всегда.',
    );
    expect(summary).toBe('Автоматическое обновление недоступно');
    expect(notifications.error).not.toHaveBeenCalled();
  });

  it('patches quote_refresh_enabled when the toggle is clicked in the DOM', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;
    const toggle = element.querySelector<HTMLInputElement>('#quote-refresh-enabled');

    expect(toggle).not.toBeNull();

    // Under Karma the standalone PrimeNG switch starts with an unset internal
    // model, so the first click syncs it with the loaded signal value and the
    // second click produces the actual user change.
    toggle?.click();
    fixture.detectChanges();
    expect(settingsService.updateSettings).not.toHaveBeenCalled();

    toggle?.click();
    fixture.detectChanges();

    expect(settingsService.updateSettings).toHaveBeenCalledOnceWith({
      quote_refresh_enabled: false,
    });
    expect(fixture.componentInstance.quoteRefreshEnabled()).toBeFalse();
  });

  it('patches only dashboard_period and reverts it on an error', () => {
    const fixture = create();

    fixture.componentInstance.onDashboardPeriodChange('3M');
    fixture.detectChanges();

    expect(settingsService.updateSettings).toHaveBeenCalledOnceWith({
      dashboard_period: '3M',
    });
    expect(fixture.componentInstance.dashboardPeriod()).toBe('3M');

    settingsService.updateSettings.and.returnValue(throwError(() => NETWORK_ERROR));
    fixture.componentInstance.onDashboardPeriodChange('ALL');
    fixture.detectChanges();

    expect(fixture.componentInstance.dashboardPeriod()).toBe('3M');
    expect(notifications.error).toHaveBeenCalled();
  });

  it('patches dashboard_period when another option is selected in the DOM', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    element.querySelector<HTMLElement>('p-select .p-select-label')?.click();
    fixture.detectChanges();

    const option = Array.from(
      document.querySelectorAll<HTMLElement>('.p-select-option'),
    ).find((candidate) => candidate.textContent?.trim() === '3 месяца');

    expect(option).withContext('опция «3 месяца» в оверлее p-select').toBeDefined();

    option?.click();
    fixture.detectChanges();

    expect(settingsService.updateSettings).toHaveBeenCalledOnceWith({
      dashboard_period: '3M',
    });
    expect(fixture.componentInstance.dashboardPeriod()).toBe('3M');
  });

  it('reports a successful quote refresh, shows the result and reloads health', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    fixture.componentInstance.refreshQuotes();
    fixture.detectChanges();

    expect(quotes.refreshAll).toHaveBeenCalledTimes(1);
    expect(health.get).toHaveBeenCalledTimes(2);
    expect(fixture.componentInstance.refreshResult()).toEqual(REFRESH_OK);
    expect(notifications.success).toHaveBeenCalled();
    expect(notifications.warn).not.toHaveBeenCalled();

    const content = textOf(element);
    expect(content).toContain('Результат обновления котировок');
    expect(content).toContain('Обновлено');
  });

  it('shows partial refresh errors as a warning and reloads health', () => {
    quotes.refreshAll.and.returnValue(of(REFRESH_PARTIAL));

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    fixture.componentInstance.refreshQuotes();
    fixture.detectChanges();

    expect(health.get).toHaveBeenCalledTimes(2);
    expect(notifications.warn).toHaveBeenCalled();
    expect(notifications.success).not.toHaveBeenCalled();

    const content = textOf(element);
    expect(content).toContain('SBER');
    expect(content).toContain('MOEX недоступен');
  });

  it('treats REFRESH_IN_PROGRESS as information, not an error', () => {
    quotes.refreshAll.and.returnValue(
      throwError(
        () => new ApiError(409, 'REFRESH_IN_PROGRESS', 'Обновление уже выполняется'),
      ),
    );

    const fixture = create();

    fixture.componentInstance.refreshQuotes();
    fixture.detectChanges();

    expect(notifications.info).toHaveBeenCalled();
    expect(notifications.error).not.toHaveBeenCalled();
    expect(health.get).toHaveBeenCalledTimes(1);
    expect(fixture.componentInstance.refreshResult()).toBeNull();
    expect((fixture.nativeElement as HTMLElement).querySelector('app-error-state')).toBeNull();
  });

  it('clears a previous refresh result when a new refresh is rejected with 409', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    fixture.componentInstance.refreshQuotes();
    fixture.detectChanges();
    expect(fixture.componentInstance.refreshResult()).toEqual(REFRESH_OK);
    expect(element.querySelector('.settings__refresh')).not.toBeNull();

    quotes.refreshAll.and.returnValue(
      throwError(
        () => new ApiError(409, 'REFRESH_IN_PROGRESS', 'Обновление уже выполняется'),
      ),
    );

    fixture.componentInstance.refreshQuotes();
    fixture.detectChanges();

    expect(fixture.componentInstance.refreshResult()).toBeNull();
    expect(element.querySelector('.settings__refresh')).toBeNull();
    expect(notifications.info).toHaveBeenCalled();
  });

  it('shows the backup path, human-readable size and creation time', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    fixture.componentInstance.createBackup();
    fixture.detectChanges();

    const content = textOf(element);
    expect(system.createBackup).toHaveBeenCalledTimes(1);
    expect(content).toContain(BACKUP.path);
    expect(content).toContain('104 КБ');
    expect(content).toContain(new DatePipe().transform(BACKUP.created_at));
    expect(content).toContain('не скачивается по HTTP');
    expect(notifications.success).toHaveBeenCalled();
  });

  it('clears a previous backup and shows an inline error when backup fails', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    fixture.componentInstance.createBackup();
    fixture.detectChanges();
    expect(fixture.componentInstance.backup()).toEqual(BACKUP);

    system.createBackup.and.returnValue(throwError(() => NETWORK_ERROR));

    fixture.componentInstance.createBackup();
    fixture.detectChanges();

    expect(fixture.componentInstance.backup()).toBeNull();
    expect(fixture.componentInstance.backupError()).toBe(NETWORK_ERROR);
    expect(notifications.error).toHaveBeenCalled();

    const content = textOf(element);
    expect(content).toContain('Резервная копия не создана');
    expect(content).toContain('Нет связи с backend');

    const backupButton = Array.from(
      element.querySelectorAll<HTMLButtonElement>('p-button button'),
    ).find((button) => button.textContent?.includes('Создать backup'));
    expect(backupButton?.disabled).toBeFalse();

    system.createBackup.and.returnValue(of(BACKUP));
    fixture.componentInstance.createBackup();
    fixture.detectChanges();

    expect(fixture.componentInstance.backupError()).toBeNull();
    expect(fixture.componentInstance.backup()).toEqual(BACKUP);
    expect(textOf(element)).toContain(BACKUP.path);
  });

  it('disables actions while refresh, backup and export are running', fakeAsync(() => {
    const refreshSubject = new Subject<QuoteRefreshResponse>();
    const backupSubject = new Subject<BackupResponse>();

    quotes.refreshAll.and.returnValue(refreshSubject.asObservable());
    system.createBackup.and.returnValue(backupSubject.asObservable());

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    fixture.componentInstance.refreshQuotes();
    fixture.detectChanges();

    expect(fixture.componentInstance.refreshing()).toBeTrue();
    expect(fixture.componentInstance.refreshButtonLabel()).toBe('Обновляем…');
    expect(element.querySelector<HTMLButtonElement>('.settings__panel-head button')?.disabled).toBeTrue();

    refreshSubject.next(REFRESH_OK);
    refreshSubject.complete();
    fixture.detectChanges();
    expect(fixture.componentInstance.refreshing()).toBeFalse();

    fixture.componentInstance.createBackup();
    fixture.detectChanges();
    expect(fixture.componentInstance.backupLoading()).toBeTrue();
    expect(textOf(element)).toContain('Создаём резервную копию');
    const backupButton = Array.from(
      element.querySelectorAll<HTMLButtonElement>('p-button button'),
    ).find((button) => button.textContent?.includes('Создать backup'));
    expect(backupButton?.disabled).toBeTrue();

    backupSubject.next(BACKUP);
    backupSubject.complete();
    fixture.detectChanges();
    expect(fixture.componentInstance.backupLoading()).toBeFalse();

    tick();
  }));

  it('downloads a JSON export using the filename from the server', fakeAsync(() => {
    const createObjectURL = spyOn(URL, 'createObjectURL').and.returnValue('blob:json');
    const revokeObjectURL = spyOn(URL, 'revokeObjectURL');
    let download = '';
    spyOn(HTMLAnchorElement.prototype, 'click').and.callFake(function (
      this: HTMLAnchorElement,
    ) {
      download = this.download;
    });

    const fixture = create();
    const blob = new Blob(['{}'], { type: 'application/json' });
    const response = new Subject<{ blob: Blob; filename: string }>();
    system.export.and.returnValue(response.asObservable());

    fixture.componentInstance.exportData('json');
    fixture.detectChanges();
    expect(fixture.componentInstance.exporting()).toBe('json');
    expect(textOf(fixture.nativeElement as HTMLElement)).toContain('Готовим файл');

    response.next({ blob, filename: 'investments-export-20261030-181012.json' });
    response.complete();
    tick();
    fixture.detectChanges();

    expect(system.export).toHaveBeenCalledWith('json');
    expect(createObjectURL).toHaveBeenCalledWith(blob);
    expect(download).toBe('investments-export-20261030-181012.json');
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:json');
    expect(fixture.componentInstance.exporting()).toBeNull();
    expect(textOf(fixture.nativeElement as HTMLElement)).toContain(
      'Файл investments-export-20261030-181012.json скачан.',
    );
    expect(notifications.success).toHaveBeenCalled();
  }));

  it('falls back to investments-export.zip for CSV when the filename is missing', fakeAsync(() => {
    spyOn(URL, 'createObjectURL').and.returnValue('blob:csv');
    const revokeObjectURL = spyOn(URL, 'revokeObjectURL');
    let download = '';
    spyOn(HTMLAnchorElement.prototype, 'click').and.callFake(function (
      this: HTMLAnchorElement,
    ) {
      download = this.download;
    });

    system.export.and.returnValue(of({ blob: new Blob(['zip']), filename: 'download' }));

    const fixture = create();
    fixture.componentInstance.exportData('csv');
    tick();

    expect(system.export).toHaveBeenCalledWith('csv');
    expect(download).toBe('investments-export.zip');
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:csv');
  }));

  it('reports export failures without creating a link', fakeAsync(() => {
    const createObjectURL = spyOn(URL, 'createObjectURL');
    const click = spyOn(HTMLAnchorElement.prototype, 'click');

    system.export.and.returnValue(throwError(() => NETWORK_ERROR));

    const fixture = create();
    fixture.componentInstance.exportData('json');
    fixture.detectChanges();

    expect(createObjectURL).not.toHaveBeenCalled();
    expect(click).not.toHaveBeenCalled();
    expect(notifications.error).toHaveBeenCalled();
    expect(textOf(fixture.nativeElement as HTMLElement)).toContain(
      'Не удалось скачать файл',
    );
  }));
});

describe('settings helpers', () => {
  it('formats backup sizes in binary units', () => {
    expect(formatFileSize(512)).toBe('512 Б');
    expect(formatFileSize(106496)).toBe('104 КБ');
    expect(formatFileSize(5 * 1024 * 1024)).toBe('5 МБ');
  });

  it('uses format-specific export fallbacks', () => {
    expect(exportFallbackFilename('json')).toBe('investments-export.json');
    expect(exportFallbackFilename('csv')).toBe('investments-export.zip');
  });
});
