import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  ViewChild,
  computed,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ConfirmationService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { SelectModule } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, forkJoin, of } from 'rxjs';

import { ApiError, mapHttpError } from '../../core/api/api-error';
import type {
  AssetDetail,
  IncomeItem,
  OperationResponse,
  PositionItem,
  PositionListResponse,
  QuoteItem,
  QuotePeriod,
} from '../../core/api/models';
import { toPriceSource } from '../../core/api/models';
import { DatePipe } from '../../core/formatting/date.pipe';
import {
  assetTypeLabel,
  currencyLabel,
  dataSourceLabel,
  incomeKindLabel,
  operationTypeLabel,
} from '../../core/formatting/labels';
import { MoneyPipe } from '../../core/formatting/money.pipe';
import { PricePipe } from '../../core/formatting/price.pipe';
import { SharePipe } from '../../core/formatting/share.pipe';
import { AssetsService } from '../../core/services/assets.service';
import { IncomeService } from '../../core/services/income.service';
import { NotificationService } from '../../core/services/notification.service';
import { OperationsService } from '../../core/services/operations.service';
import { PositionsService } from '../../core/services/positions.service';
import { QuotesService } from '../../core/services/quotes.service';
import { ErrorStateComponent } from '../../shared/ui/error-state/error-state.component';
import { EmptyStateComponent } from '../../shared/ui/empty-state/empty-state.component';
import { LoadingSkeletonComponent } from '../../shared/ui/loading-skeleton/loading-skeleton.component';
import { PageHeaderComponent } from '../../shared/ui/page-header/page-header.component';
import { PriceSourceBadgeComponent } from '../../shared/ui/price-source-badge/price-source-badge.component';
import type { SelectOption } from '../../shared/ui/select-option';
import { StatCardComponent } from '../../shared/ui/stat-card/stat-card.component';
import { OperationDialogComponent } from './operation-dialog/operation-dialog.component';

/** Asset card: position, operations, incomes and cached price history. */
@Component({
  selector: 'app-asset-detail-page',
  standalone: true,
  imports: [
    RouterLink,
    FormsModule,
    ButtonModule,
    ProgressSpinnerModule,
    SelectModule,
    TableModule,
    TagModule,
    DatePipe,
    MoneyPipe,
    PricePipe,
    SharePipe,
    PageHeaderComponent,
    StatCardComponent,
    PriceSourceBadgeComponent,
    ErrorStateComponent,
    EmptyStateComponent,
    LoadingSkeletonComponent,
    OperationDialogComponent,
  ],
  providers: [MoneyPipe, PricePipe],
  templateUrl: './asset-detail-page.html',
  styleUrl: './asset-detail-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AssetDetailPage {
  private readonly assets = inject(AssetsService);
  private readonly positionsService = inject(PositionsService);
  private readonly operationsService = inject(OperationsService);
  private readonly incomeService = inject(IncomeService);
  private readonly quotesService = inject(QuotesService);
  private readonly notifications = inject(NotificationService);
  private readonly confirmation = inject(ConfirmationService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private readonly moneyPipe = inject(MoneyPipe);
  private readonly pricePipe = inject(PricePipe);

  @ViewChild('operationsTitle')
  private readonly operationsTitle?: ElementRef<HTMLElement>;

  /** Bound from the `assets/:assetId` route via `withComponentInputBinding()`. */
  readonly assetId = input<string>();

  readonly asset = signal<AssetDetail | null>(null);
  readonly positions = signal<PositionListResponse | null>(null);
  readonly operations = signal<OperationResponse[]>([]);
  readonly incomes = signal<IncomeItem[]>([]);
  readonly quotes = signal<QuoteItem[]>([]);

  readonly loading = signal(false);
  readonly error = signal<ApiError | null>(null);
  readonly refreshing = signal(false);
  readonly deleting = signal(false);
  readonly quotesLoading = signal(false);
  readonly quotesError = signal<string | null>(null);

  readonly quotePeriod = signal<QuotePeriod>('1Y');
  readonly operationDialogVisible = signal(false);
  readonly editingOperation = signal<OperationResponse | null>(null);

  private loadSequence = 0;
  private quotesSequence = 0;
  private detailsSequence = 0;

  readonly quotePeriodOptions: SelectOption<QuotePeriod>[] = [
    { value: '1M', label: '1 месяц' },
    { value: '3M', label: '3 месяца' },
    { value: '6M', label: '6 месяцев' },
    { value: '1Y', label: '1 год' },
    { value: '3Y', label: '3 года' },
    { value: '5Y', label: '5 лет' },
    { value: 'ALL', label: 'Всё время' },
  ];

  private readonly numericId = computed(() => {
    const raw = this.assetId();
    if (!raw) {
      return null;
    }

    const value = Number(raw);
    return Number.isInteger(value) && value > 0 ? value : null;
  });

  readonly initialLoading = computed(() => this.loading() && this.asset() === null);
  readonly errorMessage = computed(() => this.error()?.message ?? '');
  readonly isBond = computed(() => this.asset()?.type === 'BOND');

  readonly position = computed<PositionItem | null>(() => {
    const assetId = this.numericId();
    if (assetId === null) {
      return null;
    }

    return this.positions()?.items.find((position) => position.asset.id === assetId) ?? null;
  });

  readonly paidIncomes = computed(() =>
    this.incomes().filter((income) => income.status === 'PAID'),
  );
  readonly expectedIncomes = computed(() =>
    this.incomes().filter((income) => income.status === 'EXPECTED'),
  );

  readonly subtitle = computed(() => {
    const asset = this.asset();
    return asset ? `${asset.secid} · ${asset.name}` : 'Позиция, операции, доходы и история цен.';
  });

  readonly assetTypeLabel = assetTypeLabel;
  readonly currencyLabel = currencyLabel;
  readonly operationTypeLabel = operationTypeLabel;
  readonly incomeKindLabel = incomeKindLabel;
  readonly dataSourceLabel = dataSourceLabel;
  readonly toPriceSource = toPriceSource;

  constructor() {
    effect(() => {
      // The router binds `assetId` after construction; the effect re-runs when
      // the input signal receives its value.
      if (!this.assetId()) {
        return;
      }

      const assetId = this.numericId();
      if (assetId === null) {
        this.error.set(new ApiError(0, 'INVALID_ASSET_ID', 'Некорректный идентификатор актива'));
        this.loading.set(false);
        return;
      }

      this.load(assetId);
    });
  }

  retry(): void {
    const assetId = this.numericId();
    if (assetId !== null) {
      this.load(assetId);
    }
  }

  currentPriceLabel(position: PositionItem): string {
    return position.current_price_type === 'PERCENT'
      ? `${this.pricePipe.transform(position.current_price)} %`
      : this.moneyPipe.transform(position.current_price);
  }

  avgPercentLabel(position: PositionItem): string {
    return position.avg_price_percent
      ? `${this.pricePipe.transform(position.avg_price_percent)} %`
      : '';
  }

  openCreateOperation(): void {
    this.editingOperation.set(null);
    this.operationDialogVisible.set(true);
  }

  openEditOperation(operation: OperationResponse): void {
    this.editingOperation.set(operation);
    this.operationDialogVisible.set(true);
  }

  onOperationSaved(): void {
    this.reloadDetails();
  }

  deleteOperation(operation: OperationResponse): void {
    this.confirmation.confirm({
      header: 'Удаление операции',
      message:
        'Удалить операцию? Если после удаления история станет некорректной, сервер отклонит операцию.',
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: 'Удалить',
      rejectLabel: 'Отмена',
      acceptButtonStyleClass: 'p-button-danger',
      accept: () => this.removeOperation(operation),
    });
  }

  confirmDeleteAsset(): void {
    const asset = this.asset();
    if (!asset) {
      return;
    }

    this.confirmation.confirm({
      header: 'Удаление актива',
      message: `Удалить актив ${asset.secid}? Удалить можно только актив без операций и выплаченных доходов.`,
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: 'Удалить',
      rejectLabel: 'Отмена',
      acceptButtonStyleClass: 'p-button-danger',
      accept: () => this.deleteAsset(asset.id),
    });
  }

  refreshAsset(): void {
    const assetId = this.numericId();
    if (assetId === null || this.refreshing()) {
      return;
    }

    this.refreshing.set(true);

    this.assets
      .refresh(assetId)
      .pipe(
        finalize(() => this.refreshing.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (asset) => {
          if (this.numericId() !== assetId) {
            return;
          }

          this.asset.set(asset);
          this.notifications.success('Данные актива и котировки обновлены');
          this.reloadDetails();
          this.loadQuotes(assetId, this.quotePeriod());
        },
        error: (error: unknown) => {
          if (this.numericId() === assetId) {
            this.notifications.error(mapHttpError(error), 'Не удалось обновить актив');
          }
        },
      });
  }

  onQuotePeriodChange(period: QuotePeriod): void {
    const assetId = this.numericId();
    if (assetId === null || period === this.quotePeriod()) {
      return;
    }

    this.quotePeriod.set(period);
    this.loadQuotes(assetId, period);
  }

  retryQuotes(): void {
    const assetId = this.numericId();
    if (assetId !== null) {
      this.loadQuotes(assetId, this.quotePeriod());
    }
  }

  private load(assetId: number): void {
    const sequence = ++this.loadSequence;
    this.detailsSequence += 1;

    this.loading.set(true);
    this.error.set(null);
    this.asset.set(null);
    this.positions.set(null);
    this.operations.set([]);
    this.incomes.set([]);
    this.quotes.set([]);
    this.quotesError.set(null);
    this.quotesSequence += 1;
    this.quotesLoading.set(false);

    forkJoin({
      asset: this.assets.get(assetId),
      positions: this.positionsService.getPositions(),
      operations: this.operationsService.list({ assetId }),
      incomes: this.incomeService.list({ assetId }),
    })
      .pipe(
        finalize(() => {
          if (sequence === this.loadSequence) {
            this.loading.set(false);
          }
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: ({ asset, positions, operations, incomes }) => {
          if (sequence !== this.loadSequence) {
            return;
          }

          this.asset.set(asset);
          this.positions.set(positions);
          this.operations.set(operations.items);
          this.incomes.set(incomes.items);
          this.loadQuotes(assetId, this.quotePeriod());
        },
        error: (error: unknown) => {
          if (sequence === this.loadSequence) {
            this.error.set(mapHttpError(error));
          }
        },
      });
  }

  private loadQuotes(assetId: number, period: QuotePeriod): void {
    const sequence = ++this.quotesSequence;

    this.quotesLoading.set(true);
    this.quotesError.set(null);

    this.quotesService
      .history(assetId, period)
      .pipe(
        catchError((error: unknown) => {
          if (sequence === this.quotesSequence) {
            this.quotesError.set(mapHttpError(error).message);
          }
          return of(null);
        }),
        finalize(() => {
          if (sequence === this.quotesSequence) {
            this.quotesLoading.set(false);
          }
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((response) => {
        if (sequence === this.quotesSequence) {
          this.quotes.set(response?.items ?? []);
        }
      });
  }

  private reloadDetails(): void {
    const assetId = this.numericId();
    if (assetId === null) {
      return;
    }

    const sequence = ++this.detailsSequence;

    forkJoin({
      positions: this.positionsService.getPositions(),
      operations: this.operationsService.list({ assetId }),
      incomes: this.incomeService.list({ assetId }),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ positions, operations, incomes }) => {
          if (sequence !== this.detailsSequence || this.numericId() !== assetId) {
            return;
          }

          this.positions.set(positions);
          this.operations.set(operations.items);
          this.incomes.set(incomes.items);
        },
        error: (error: unknown) => {
          if (sequence === this.detailsSequence) {
            this.notifications.error(mapHttpError(error), 'Не удалось обновить карточку актива');
          }
        },
      });
  }

  private removeOperation(operation: OperationResponse): void {
    this.operationsService
      .remove(operation.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.notifications.success('Операция удалена');
          this.operationsTitle?.nativeElement.focus();
          this.reloadDetails();
        },
        error: (error: unknown) => {
          this.notifications.error(mapHttpError(error), 'Не удалось удалить операцию');
        },
      });
  }

  private deleteAsset(assetId: number): void {
    this.deleting.set(true);

    this.assets
      .remove(assetId)
      .pipe(
        finalize(() => this.deleting.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: () => {
          this.notifications.success('Актив удалён');
          if (this.numericId() === assetId) {
            void this.router.navigate(['/portfolio']).then(() => {
              document.getElementById('main-content')?.focus();
            });
          }
        },
        error: (error: unknown) => {
          if (this.numericId() === assetId) {
            this.notifications.error(mapHttpError(error), 'Не удалось удалить актив');
          }
        },
      });
  }
}
