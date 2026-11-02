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
import { RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { finalize } from 'rxjs';

import { mapHttpError } from '../../core/api/api-error';
import type { ApiError } from '../../core/api/api-error';
import type { DashboardResponse, DashboardSeriesPointOut, Period } from '../../core/api/models';
import { toPeriod } from '../../core/api/models';
import { DatePipe } from '../../core/formatting/date.pipe';
import { currencyLabel } from '../../core/formatting/labels';
import { MoneyPipe } from '../../core/formatting/money.pipe';
import { DashboardService } from '../../core/services/dashboard.service';
import { NotificationService } from '../../core/services/notification.service';
import { EmptyStateComponent } from '../../shared/ui/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/ui/error-state/error-state.component';
import { LoadingSkeletonComponent } from '../../shared/ui/loading-skeleton/loading-skeleton.component';
import { PageHeaderComponent } from '../../shared/ui/page-header/page-header.component';
import { PeriodSwitcherComponent } from '../../shared/ui/period-switcher/period-switcher.component';
import { PositionsTableComponent } from '../../shared/ui/positions-table/positions-table.component';
import { StatCardComponent } from '../../shared/ui/stat-card/stat-card.component';
import { ValueChartComponent } from '../../shared/ui/value-chart/value-chart.component';

const PERIOD_LABELS: Record<Period, string> = {
  '1M': '1 месяц',
  '3M': '3 месяца',
  '1Y': '1 год',
  ALL: 'всё время',
};

/** Dashboard: totals, value chart, open positions and upcoming coupons. */
@Component({
  selector: 'app-dashboard-page',
  standalone: true,
  imports: [
    RouterLink,
    ButtonModule,
    MessageModule,
    ProgressSpinnerModule,
    DatePipe,
    MoneyPipe,
    PageHeaderComponent,
    StatCardComponent,
    PeriodSwitcherComponent,
    PositionsTableComponent,
    ValueChartComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingSkeletonComponent,
  ],
  providers: [DatePipe],
  templateUrl: './dashboard-page.html',
  styleUrl: './dashboard-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardPage implements OnInit {
  private readonly dashboard = inject(DashboardService);
  private readonly notifications = inject(NotificationService);
  private readonly datePipe = inject(DatePipe);
  private readonly destroyRef = inject(DestroyRef);

  readonly data = signal<DashboardResponse | null>(null);
  readonly loading = signal(false);
  readonly error = signal<ApiError | null>(null);
  readonly selectedPeriod = signal<Period>('1Y');

  private readonly lastRequestedPeriod = signal<Period | null>(null);
  private requestSequence = 0;

  readonly initialLoading = computed(() => this.loading() && this.data() === null);
  readonly isEmpty = computed(() => (this.data()?.positions.length ?? 0) === 0);
  readonly hasAssets = computed(() => (this.data()?.totals.assets_count ?? 0) > 0);
  readonly emptyTitle = computed(() =>
    this.hasAssets() ? 'Нет открытых позиций' : 'Портфель пуст',
  );
  readonly emptyMessage = computed(() =>
    this.hasAssets()
      ? 'Активы добавлены, но операций пока нет. Откройте портфель и внесите первую покупку.'
      : 'Добавьте актив и первую операцию, чтобы увидеть итоги, динамику стоимости и ближайшие купоны.',
  );
  readonly errorMessage = computed(() => this.error()?.message ?? '');

  readonly subtitle = computed(() => {
    const dashboard = this.data();
    if (!dashboard) {
      return 'Сводка по портфелю: стоимость, вложенные средства и выплаты.';
    }

    return `Данные на ${this.datePipe.transform(dashboard.as_of)} · ${currencyLabel(dashboard.currency)}`;
  });

  readonly positionsHint = computed(() => {
    const totals = this.data()?.totals;
    return totals ? `Позиций: ${totals.positions_count} · активов: ${totals.assets_count}` : '';
  });

  readonly chartSeries = computed<readonly DashboardSeriesPointOut[]>(
    () => this.data()?.series ?? [],
  );

  readonly currencyLabel = currencyLabel;

  ngOnInit(): void {
    // The first request intentionally omits `period`: the backend applies the
    // stored `dashboard_period` preference and returns the resolved period.
    this.load();
  }

  retry(): void {
    this.load(this.lastRequestedPeriod() ?? undefined);
  }

  onPeriodChange(period: Period): void {
    if (period === this.selectedPeriod()) {
      return;
    }

    this.selectedPeriod.set(period);
    this.load(period);
  }

  periodLabel(period: Period): string {
    return PERIOD_LABELS[period];
  }

  private load(period?: Period): void {
    const sequence = ++this.requestSequence;

    this.loading.set(true);
    this.error.set(null);
    this.lastRequestedPeriod.set(period ?? null);

    const request$ =
      period === undefined ? this.dashboard.getDashboard() : this.dashboard.getDashboard(period);

    request$
      .pipe(
        takeUntilDestroyed(this.destroyRef),
        finalize(() => {
          if (sequence === this.requestSequence) {
            this.loading.set(false);
          }
        }),
      )
      .subscribe({
        next: (response) => {
          if (sequence !== this.requestSequence) {
            return;
          }

          this.data.set(response);

          const resolvedPeriod = toPeriod(response.period);
          if (resolvedPeriod) {
            this.selectedPeriod.set(resolvedPeriod);
          }
        },
        error: (error: unknown) => {
          if (sequence !== this.requestSequence) {
            return;
          }

          const apiError = mapHttpError(error);

          // Keep the last good dashboard visible; only a failed initial load
          // replaces the page with an error block.
          const lastGood = this.data();
          if (lastGood) {
            const lastPeriod = toPeriod(lastGood.period);
            if (lastPeriod) {
              this.selectedPeriod.set(lastPeriod);
            }
            this.notifications.error(apiError, 'Не удалось обновить дашборд');
          } else {
            this.error.set(apiError);
          }
        },
      });
  }
}
