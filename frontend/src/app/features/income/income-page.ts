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
import { RouterLink } from '@angular/router';
import { ConfirmationService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { DatePickerModule } from 'primeng/datepicker';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { SelectModule } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { TabsModule } from 'primeng/tabs';
import { TagModule } from 'primeng/tag';
import { finalize } from 'rxjs';

import { mapHttpError } from '../../core/api/api-error';
import type { ApiError } from '../../core/api/api-error';
import type {
  AssetListItem,
  IncomeItem,
  IncomeKind,
  IncomeListResponse,
  IncomeStatus,
} from '../../core/api/models';
import { toIsoDate } from '../../core/formatting/date-input';
import { DatePipe } from '../../core/formatting/date.pipe';
import {
  dataSourceLabel,
  incomeKindLabel,
  incomeStatusLabel,
} from '../../core/formatting/labels';
import { MoneyPipe } from '../../core/formatting/money.pipe';
import { AssetsService } from '../../core/services/assets.service';
import { IncomeService } from '../../core/services/income.service';
import type { IncomeFilters } from '../../core/services/income.service';
import { NotificationService } from '../../core/services/notification.service';
import { EmptyStateComponent } from '../../shared/ui/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/ui/error-state/error-state.component';
import { LoadingSkeletonComponent } from '../../shared/ui/loading-skeleton/loading-skeleton.component';
import { PageHeaderComponent } from '../../shared/ui/page-header/page-header.component';
import type { SelectOption } from '../../shared/ui/select-option';
import { StatCardComponent } from '../../shared/ui/stat-card/stat-card.component';
import { IncomeFormDialogComponent } from './income-form-dialog/income-form-dialog.component';
import { toIncomeAssetOptions } from './income-options';
import { MarkPaidDialogComponent } from './mark-paid-dialog/mark-paid-dialog.component';

/** Income list: paid/expected tabs, portfolio totals, filters and CRUD. */
@Component({
  selector: 'app-income-page',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    ButtonModule,
    DatePickerModule,
    ProgressSpinnerModule,
    SelectModule,
    TableModule,
    TabsModule,
    TagModule,
    DatePipe,
    MoneyPipe,
    PageHeaderComponent,
    StatCardComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingSkeletonComponent,
    IncomeFormDialogComponent,
    MarkPaidDialogComponent,
  ],
  providers: [DatePipe],
  templateUrl: './income-page.html',
  styleUrl: './income-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class IncomePage implements OnInit {
  private readonly incomeService = inject(IncomeService);
  private readonly assetsService = inject(AssetsService);
  private readonly notifications = inject(NotificationService);
  private readonly confirmation = inject(ConfirmationService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly datePipe = inject(DatePipe);

  readonly data = signal<IncomeListResponse | null>(null);
  readonly assets = signal<AssetListItem[]>([]);
  readonly loading = signal(false);
  readonly error = signal<ApiError | null>(null);

  readonly status = signal<IncomeStatus>('PAID');
  readonly kind = signal<IncomeKind | null>(null);
  readonly assetId = signal<number | null>(null);
  readonly from = signal<Date | null>(null);
  readonly to = signal<Date | null>(null);

  readonly formVisible = signal(false);
  readonly editingIncome = signal<IncomeItem | null>(null);
  readonly markPaidVisible = signal(false);
  readonly markingPaidIncome = signal<IncomeItem | null>(null);
  readonly deletingIncomeId = signal<number | null>(null);

  readonly kindOptions: SelectOption<IncomeKind>[] = [
    { value: 'DIVIDEND', label: 'Дивиденд' },
    { value: 'COUPON', label: 'Купон' },
  ];

  readonly incomeKindLabel = incomeKindLabel;
  readonly incomeStatusLabel = incomeStatusLabel;
  readonly dataSourceLabel = dataSourceLabel;

  private requestSequence = 0;
  private assetsWarningShown = false;

  readonly initialLoading = computed(() => this.loading() && this.data() === null);
  readonly errorMessage = computed(() => this.error()?.message ?? '');
  readonly items = computed<IncomeItem[]>(() => this.data()?.items ?? []);
  readonly isEmpty = computed(() => this.items().length === 0);
  readonly hasFilters = computed(
    () => this.kind() !== null || this.assetId() !== null || this.from() !== null || this.to() !== null,
  );
  readonly listHeading = computed(() =>
    this.status() === 'PAID' ? 'Выплаченные' : 'Ожидаемые купоны',
  );
  readonly itemCount = computed(() => this.items().length);

  readonly assetOptions = computed<SelectOption<number>[]>(() =>
    toIncomeAssetOptions(this.assets()),
  );

  readonly emptyTitle = computed(() => {
    if (this.hasFilters()) {
      return 'По выбранным фильтрам доходов нет';
    }

    return this.status() === 'PAID'
      ? 'Выплаченных доходов пока нет'
      : 'Ожидаемых купонов нет';
  });

  readonly emptyMessage = computed(() => {
    if (this.hasFilters()) {
      return 'Измените условия фильтра или сбросьте их, чтобы увидеть все доходы.';
    }

    return this.status() === 'PAID'
      ? 'Добавьте выплату вручную — дивиденд или купон, который уже получен.'
      : 'Купоны появятся после синхронизации расписания MOEX или добавления ожидаемой выплаты.';
  });

  ngOnInit(): void {
    this.loadAssets();
    this.load();
  }

  retry(): void {
    this.loadAssets();
    this.load({ reset: true });
  }

  onStatusChange(value: string | number | undefined): void {
    const status: IncomeStatus = value === 'EXPECTED' ? 'EXPECTED' : 'PAID';

    if (status === this.status()) {
      return;
    }

    this.status.set(status);
    this.load({ reset: true });
  }

  onKindChange(kind: IncomeKind | null): void {
    this.kind.set(kind);
    this.load({ reset: true });
  }

  onAssetChange(assetId: number | null): void {
    this.assetId.set(assetId);
    this.load({ reset: true });
  }

  onFromChange(from: Date | null): void {
    this.from.set(from);
    this.load({ reset: true });
  }

  onToChange(to: Date | null): void {
    this.to.set(to);
    this.load({ reset: true });
  }

  resetFilters(): void {
    if (!this.hasFilters()) {
      return;
    }

    this.kind.set(null);
    this.assetId.set(null);
    this.from.set(null);
    this.to.set(null);
    this.load({ reset: true });
  }

  openCreate(): void {
    this.editingIncome.set(null);
    this.formVisible.set(true);
  }

  openEdit(income: IncomeItem): void {
    this.editingIncome.set(income);
    this.formVisible.set(true);
  }

  openMarkPaid(income: IncomeItem): void {
    this.markingPaidIncome.set(income);
    this.markPaidVisible.set(true);
  }

  onIncomeSaved(income: IncomeItem): void {
    // A manually added income is always PAID: switch to the matching tab so
    // the new row is visible even when it was created from EXPECTED.
    if (income.status !== this.status()) {
      this.status.set(income.status);
      this.load({ reset: true });
      return;
    }

    this.load();
  }

  onIncomePaid(): void {
    this.load();
  }

  onIncomeStale(): void {
    // A repeated mark-paid means the row is already PAID; reload so the stale
    // EXPECTED row is not left on screen.
    this.load();
  }

  deleteIncome(income: IncomeItem): void {
    const expected = income.status === 'EXPECTED';
    const warning = expected
      ? ' Это ожидаемый купон: при следующей синхронизации MOEX может создать его снова.'
      : '';

    this.confirmation.confirm({
      header: 'Удаление дохода',
      message: `Удалить ${incomeKindLabel(income.kind).toLowerCase()} ${income.asset_secid} от ${this.datePipe.transform(income.pay_date)}?${warning}`,
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: 'Удалить',
      rejectLabel: 'Отмена',
      acceptButtonStyleClass: 'p-button-danger',
      accept: () => this.removeIncome(income),
    });
  }

  private loadAssets(): void {
    this.assetsService
      .list()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.assets.set(response.items);
          this.assetsWarningShown = false;
        },
        error: () => {
          if (this.assetsWarningShown) {
            return;
          }

          this.assetsWarningShown = true;
          this.notifications.warn(
            'Не удалось загрузить список активов. Фильтр по тикеру временно недоступен.',
          );
        },
      });
  }

  private load(options: { reset?: boolean } = {}): void {
    const sequence = ++this.requestSequence;

    this.loading.set(true);
    this.error.set(null);

    if (options.reset) {
      this.data.set(null);
    }

    this.incomeService
      .list(this.buildFilters())
      .pipe(
        finalize(() => {
          if (sequence === this.requestSequence) {
            this.loading.set(false);
          }
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (response) => {
          if (sequence !== this.requestSequence) {
            return;
          }

          this.data.set(response);
        },
        error: (error: unknown) => {
          if (sequence !== this.requestSequence) {
            return;
          }

          const apiError = mapHttpError(error);
          if (this.data()) {
            this.notifications.error(apiError, 'Не удалось загрузить доходы');
            return;
          }

          this.error.set(apiError);
        },
      });
  }

  private buildFilters(): IncomeFilters {
    return {
      status: this.status(),
      kind: this.kind() ?? undefined,
      assetId: this.assetId() ?? undefined,
      from: toIsoDate(this.from()) ?? undefined,
      to: toIsoDate(this.to()) ?? undefined,
    };
  }

  private removeIncome(income: IncomeItem): void {
    if (this.deletingIncomeId() !== null) {
      return;
    }

    this.deletingIncomeId.set(income.id);

    this.incomeService
      .remove(income.id)
      .pipe(
        finalize(() => this.deletingIncomeId.set(null)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: () => {
          this.notifications.success('Доход удалён');
          this.load();
        },
        error: (error: unknown) => {
          this.notifications.error(mapHttpError(error), 'Не удалось удалить доход');
        },
      });
  }
}
