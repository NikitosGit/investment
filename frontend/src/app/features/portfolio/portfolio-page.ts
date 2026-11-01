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
import { Router } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { SelectButtonModule } from 'primeng/selectbutton';
import { finalize } from 'rxjs';

import { mapHttpError } from '../../core/api/api-error';
import type { ApiError } from '../../core/api/api-error';
import type {
  AssetDetail,
  AssetType,
  PositionItem,
  PositionListResponse,
} from '../../core/api/models';
import { MoneyPipe } from '../../core/formatting/money.pipe';
import { NotificationService } from '../../core/services/notification.service';
import { PositionsService } from '../../core/services/positions.service';
import { EmptyStateComponent } from '../../shared/ui/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/ui/error-state/error-state.component';
import { LoadingSkeletonComponent } from '../../shared/ui/loading-skeleton/loading-skeleton.component';
import { PageHeaderComponent } from '../../shared/ui/page-header/page-header.component';
import { PositionsTableComponent } from '../../shared/ui/positions-table/positions-table.component';
import { StatCardComponent } from '../../shared/ui/stat-card/stat-card.component';
import { AssetSearchDialogComponent } from './asset-search-dialog/asset-search-dialog.component';

type PortfolioFilter = AssetType | 'ALL';

interface FilterOption {
  value: PortfolioFilter;
  label: string;
}

/** Portfolio: open positions, totals, type filter and asset search. */
@Component({
  selector: 'app-portfolio-page',
  standalone: true,
  imports: [
    FormsModule,
    ButtonModule,
    SelectButtonModule,
    MoneyPipe,
    PageHeaderComponent,
    StatCardComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingSkeletonComponent,
    PositionsTableComponent,
    AssetSearchDialogComponent,
  ],
  templateUrl: './portfolio-page.html',
  styleUrl: './portfolio-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PortfolioPage implements OnInit {
  private readonly positionsService = inject(PositionsService);
  private readonly notifications = inject(NotificationService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly data = signal<PositionListResponse | null>(null);
  readonly loading = signal(false);
  readonly error = signal<ApiError | null>(null);
  readonly filter = signal<PortfolioFilter>('ALL');
  readonly assetSearchVisible = signal(false);

  readonly filterOptions: FilterOption[] = [
    { value: 'ALL', label: 'Все' },
    { value: 'STOCK', label: 'Акции' },
    { value: 'BOND', label: 'Облигации' },
  ];

  readonly initialLoading = computed(() => this.loading() && this.data() === null);
  readonly isEmpty = computed(() => (this.data()?.items.length ?? 0) === 0);
  readonly errorMessage = computed(() => this.error()?.message ?? '');
  readonly positionCount = computed(() => this.data()?.items.length ?? 0);

  readonly filtered = computed<PositionItem[]>(() => {
    const items = this.data()?.items ?? [];
    const filter = this.filter();

    return filter === 'ALL' ? items : items.filter((position) => position.asset.type === filter);
  });

  readonly filterEmpty = computed(() => !this.isEmpty() && this.filtered().length === 0);

  readonly composition = computed(() => {
    const items = this.data()?.items ?? [];
    const stocks = items.filter((position) => position.asset.type === 'STOCK').length;
    const bonds = items.filter((position) => position.asset.type === 'BOND').length;
    return `Акций: ${stocks} · облигаций: ${bonds}`;
  });

  ngOnInit(): void {
    this.load();
  }

  retry(): void {
    this.load();
  }

  onFilterChange(value: PortfolioFilter): void {
    this.filter.set(value);
  }

  resetFilter(): void {
    this.filter.set('ALL');
  }

  openAssetSearch(): void {
    this.assetSearchVisible.set(true);
  }

  onAssetAdded(asset: AssetDetail): void {
    this.notifications.success(
      `${asset.secid} добавлен в портфель. Теперь можно внести операцию.`,
      'Актив добавлен',
    );
    void this.router.navigate(['/assets', asset.id]);
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);

    this.positionsService
      .getPositions()
      .pipe(
        finalize(() => this.loading.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (response) => this.data.set(response),
        error: (error: unknown) => this.error.set(mapHttpError(error)),
      });
  }
}
