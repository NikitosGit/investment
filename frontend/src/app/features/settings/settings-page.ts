import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { SelectModule } from 'primeng/select';
import { TagModule } from 'primeng/tag';
import { ToggleSwitchModule } from 'primeng/toggleswitch';
import { finalize } from 'rxjs';

import { mapHttpError } from '../../core/api/api-error';
import type { ApiError } from '../../core/api/api-error';
import type {
  BackupResponse,
  HealthResponse,
  Period,
  QuoteRefreshResponse,
  SettingsResponse,
  SettingsUpdate,
} from '../../core/api/models';
import { DatePipe } from '../../core/formatting/date.pipe';
import { HealthService } from '../../core/services/health.service';
import { NotificationService } from '../../core/services/notification.service';
import { QuotesService } from '../../core/services/quotes.service';
import { SettingsService } from '../../core/services/settings.service';
import { SystemService } from '../../core/services/system.service';
import type { ExportFormat } from '../../core/services/system.service';
import { ErrorStateComponent } from '../../shared/ui/error-state/error-state.component';
import { LoadingSkeletonComponent } from '../../shared/ui/loading-skeleton/loading-skeleton.component';
import { PageHeaderComponent } from '../../shared/ui/page-header/page-header.component';
import type { SelectOption } from '../../shared/ui/select-option';

export type BadgeSeverity = 'success' | 'info' | 'warn' | 'danger' | 'secondary';

type SettingsField = 'quote_refresh_enabled' | 'dashboard_period';

const PERIOD_OPTIONS: SelectOption<Period>[] = [
  { value: '1M', label: '1 месяц' },
  { value: '3M', label: '3 месяца' },
  { value: '1Y', label: '1 год' },
  { value: 'ALL', label: 'Все данные' },
];

/** Status text for the health card; the badge repeats it instead of using color alone. */
export function healthStatusLabel(status: HealthResponse['status']): string {
  return status === 'ok' ? 'Работает' : 'Ограничена';
}

export function healthStatusSeverity(status: HealthResponse['status']): BadgeSeverity {
  return status === 'ok' ? 'success' : 'warn';
}

export function databaseStatusLabel(status: HealthResponse['database']): string {
  return status === 'ok' ? 'Доступна' : 'Ошибка';
}

export function databaseStatusSeverity(status: HealthResponse['database']): BadgeSeverity {
  return status === 'ok' ? 'success' : 'danger';
}

export function moexStatusLabel(status: HealthResponse['moex']): string {
  switch (status) {
    case 'ok':
      return 'Доступен';
    case 'error':
      return 'Недоступен';
    default:
      return 'Не проверялся';
  }
}

export function moexStatusSeverity(status: HealthResponse['moex']): BadgeSeverity {
  switch (status) {
    case 'ok':
      return 'success';
    case 'error':
      return 'danger';
    default:
      return 'secondary';
  }
}

/** Human-readable file size for the backup result (not a monetary value). */
export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return '—';
  }

  const units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ'];
  let value = bytes;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  const formatter = new Intl.NumberFormat('ru-RU', {
    maximumFractionDigits: unitIndex === 0 ? 0 : 1,
  });

  return `${formatter.format(value)} ${units[unitIndex]}`;
}

/** Fallback download names when `Content-Disposition` is unavailable. */
export function exportFallbackFilename(format: ExportFormat): string {
  return format === 'csv' ? 'investments-export.zip' : 'investments-export.json';
}

/** Settings and system operations: health, quotes refresh, options, backup, export. */
@Component({
  selector: 'app-settings-page',
  standalone: true,
  imports: [
    FormsModule,
    ButtonModule,
    SelectModule,
    TagModule,
    ToggleSwitchModule,
    DatePipe,
    PageHeaderComponent,
    ErrorStateComponent,
    LoadingSkeletonComponent,
  ],
  templateUrl: './settings-page.html',
  styleUrl: './settings-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsPage implements OnInit {
  private readonly healthService = inject(HealthService);
  private readonly settingsService = inject(SettingsService);
  private readonly quotesService = inject(QuotesService);
  private readonly systemService = inject(SystemService);
  private readonly notifications = inject(NotificationService);
  private readonly destroyRef = inject(DestroyRef);

  readonly health = signal<HealthResponse | null>(null);
  readonly healthLoading = signal(false);
  readonly healthError = signal<ApiError | null>(null);
  readonly refreshing = signal(false);
  readonly refreshResult = signal<QuoteRefreshResponse | null>(null);

  readonly settings = signal<SettingsResponse | null>(null);
  readonly settingsLoading = signal(false);
  readonly settingsError = signal<ApiError | null>(null);
  readonly quoteRefreshEnabled = signal(false);
  readonly dashboardPeriod = signal<Period>('1Y');
  readonly savingField = signal<SettingsField | null>(null);

  readonly backup = signal<BackupResponse | null>(null);
  readonly backupLoading = signal(false);
  readonly backupError = signal<ApiError | null>(null);
  readonly exporting = signal<ExportFormat | null>(null);
  readonly exportStatus = signal('');

  readonly periodOptions = PERIOD_OPTIONS;

  readonly healthStatusLabel = healthStatusLabel;
  readonly healthStatusSeverity = healthStatusSeverity;
  readonly databaseStatusLabel = databaseStatusLabel;
  readonly databaseStatusSeverity = databaseStatusSeverity;
  readonly moexStatusLabel = moexStatusLabel;
  readonly moexStatusSeverity = moexStatusSeverity;
  readonly formatFileSize = formatFileSize;

  readonly healthErrorMessage = computed(() => this.healthError()?.message ?? '');
  readonly settingsErrorMessage = computed(() => this.settingsError()?.message ?? '');
  readonly backupErrorMessage = computed(() => this.backupError()?.message ?? '');
  readonly initialHealthLoading = computed(() => this.healthLoading() && !this.health());
  readonly initialSettingsLoading = computed(
    () => this.settingsLoading() && !this.settings(),
  );
  readonly refreshButtonLabel = computed(() =>
    this.refreshing() ? 'Обновляем…' : 'Обновить котировки',
  );
  readonly saving = computed(() => this.savingField() !== null);

  ngOnInit(): void {
    this.loadHealth();
    this.loadSettings();
  }

  /** Load or reload the health card independently from the settings card. */
  loadHealth(): void {
    if (this.healthLoading()) {
      return;
    }

    this.healthLoading.set(true);
    this.healthError.set(null);

    this.healthService
      .get()
      .pipe(
        finalize(() => this.healthLoading.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (health) => this.health.set(health),
        error: (error: unknown) => {
          const apiError = mapHttpError(error);

          if (this.health()) {
            this.notifications.error(apiError, 'Не удалось обновить состояние системы');
            return;
          }

          this.healthError.set(apiError);
        },
      });
  }

  /** Load or reload the settings card independently from the health card. */
  loadSettings(): void {
    if (this.settingsLoading()) {
      return;
    }

    this.settingsLoading.set(true);
    this.settingsError.set(null);

    this.settingsService
      .getSettings()
      .pipe(
        finalize(() => this.settingsLoading.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (settings) => {
          this.settings.set(settings);
          this.applySettings(settings);
        },
        error: (error: unknown) => {
          const apiError = mapHttpError(error);

          if (this.settings()) {
            this.notifications.error(apiError, 'Не удалось обновить настройки');
            return;
          }

          this.settingsError.set(apiError);
        },
      });
  }

  refreshQuotes(): void {
    if (this.refreshing()) {
      return;
    }

    this.refreshing.set(true);
    this.refreshResult.set(null);

    this.quotesService
      .refreshAll()
      .pipe(
        finalize(() => this.refreshing.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (result) => {
          this.refreshResult.set(result);

          if (result.failed > 0 || result.errors.length > 0) {
            this.notifications.warn(
              `Обновлено: ${result.updated}, с ошибками: ${result.failed}. Подробности — под кнопкой обновления.`,
              'Обновление завершено с ошибками',
            );
          } else {
            this.notifications.success(`Котировки обновлены: ${result.updated}.`);
          }

          // Dashboard and positions are not cached, so they will be fetched
          // fresh on the next visit. Only the health card needs a reload here.
          this.loadHealth();
        },
        error: (error: unknown) => {
          const apiError = mapHttpError(error);

          if (apiError.status === 409 && apiError.code === 'REFRESH_IN_PROGRESS') {
            this.refreshResult.set(null);
            this.notifications.info(
              'Обновление котировок уже выполняется. Дождитесь завершения — повторный запуск не нужен.',
              'Обновление уже идёт',
            );
            return;
          }

          this.notifications.error(apiError, 'Не удалось обновить котировки');
        },
      });
  }

  onQuoteRefreshChange(enabled: boolean): void {
    if (this.saving() || enabled === this.quoteRefreshEnabled()) {
      return;
    }

    const previous = this.quoteRefreshEnabled();
    this.quoteRefreshEnabled.set(enabled);

    this.saveSettings(
      { quote_refresh_enabled: enabled },
      () => this.quoteRefreshEnabled.set(previous),
      'quote_refresh_enabled',
    );
  }

  onDashboardPeriodChange(period: Period | null): void {
    if (this.saving() || period === null || period === this.dashboardPeriod()) {
      return;
    }

    const previous = this.dashboardPeriod();
    this.dashboardPeriod.set(period);

    this.saveSettings(
      { dashboard_period: period },
      () => this.dashboardPeriod.set(previous),
      'dashboard_period',
    );
  }

  createBackup(): void {
    if (this.backupLoading()) {
      return;
    }

    this.backupLoading.set(true);
    this.backup.set(null);
    this.backupError.set(null);

    this.systemService
      .createBackup()
      .pipe(
        finalize(() => this.backupLoading.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (backup) => {
          this.backup.set(backup);
          this.backupError.set(null);
          this.notifications.success('Резервная копия создана на сервере.');
        },
        error: (error: unknown) => {
          const apiError = mapHttpError(error);
          this.backupError.set(apiError);
          this.notifications.error(
            apiError,
            'Не удалось создать резервную копию',
          );
        },
      });
  }

  exportData(format: ExportFormat): void {
    if (this.exporting() !== null) {
      return;
    }

    this.exporting.set(format);
    this.exportStatus.set('');

    this.systemService
      .export(format)
      .pipe(
        finalize(() => this.exporting.set(null)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (file) => {
          const filename =
            file.filename && file.filename !== 'download'
              ? file.filename
              : exportFallbackFilename(format);

          this.triggerDownload(file.blob, filename);
          this.exportStatus.set(`Файл ${filename} скачан.`);
          this.notifications.success(
            format === 'csv' ? 'Экспорт CSV готов.' : 'Экспорт JSON готов.',
          );
        },
        error: (error: unknown) => {
          const apiError = mapHttpError(error);
          this.exportStatus.set(`Не удалось скачать файл: ${apiError.message}.`);
          this.notifications.error(apiError, 'Не удалось экспортировать данные');
        },
      });
  }

  private saveSettings(
    payload: SettingsUpdate,
    revert: () => void,
    field: SettingsField,
  ): void {
    this.savingField.set(field);

    this.settingsService
      .updateSettings(payload)
      .pipe(
        finalize(() => this.savingField.set(null)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (settings) => {
          this.settings.set(settings);
          this.applySettings(settings);
          this.notifications.success('Настройки сохранены.');
        },
        error: (error: unknown) => {
          revert();
          const apiError = mapHttpError(error);

          if (field === 'quote_refresh_enabled' && apiError.status === 400) {
            this.notifications.warn(
              'Автоматическое обновление отключено настройками развёртывания: включить его можно только на сервере. Ручное обновление котировок доступно всегда.',
              'Автоматическое обновление недоступно',
            );
            return;
          }

          this.notifications.error(apiError, 'Не удалось сохранить настройки');
        },
      });
  }

  private applySettings(settings: SettingsResponse): void {
    this.quoteRefreshEnabled.set(settings.quote_refresh_enabled);
    this.dashboardPeriod.set(settings.dashboard_period);
  }

  private triggerDownload(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');

    anchor.href = url;
    anchor.download = filename;
    anchor.rel = 'noopener';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();

    // Revoke on the next tick so the browser can start the download.
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}
