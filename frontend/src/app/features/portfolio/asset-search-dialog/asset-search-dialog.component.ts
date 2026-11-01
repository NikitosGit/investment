import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  model,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { TagModule } from 'primeng/tag';
import {
  Subject,
  catchError,
  debounceTime,
  finalize,
  map,
  merge,
  of,
  switchMap,
} from 'rxjs';

import { mapHttpError } from '../../../core/api/api-error';
import type { ApiError } from '../../../core/api/api-error';
import type {
  AssetDetail,
  AssetSearchItem,
  AssetSearchResponse,
} from '../../../core/api/models';
import { assetTypeLabel } from '../../../core/formatting/labels';
import { AssetsService } from '../../../core/services/assets.service';

/** Search MOEX and add a security to the local portfolio. */
@Component({
  selector: 'app-asset-search-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    ButtonModule,
    DialogModule,
    InputTextModule,
    MessageModule,
    ProgressSpinnerModule,
    TagModule,
  ],
  templateUrl: './asset-search-dialog.component.html',
  styleUrl: './asset-search-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AssetSearchDialogComponent {
  private readonly assets = inject(AssetsService);
  private readonly destroyRef = inject(DestroyRef);

  readonly visible = model(false);
  readonly added = output<AssetDetail>();

  readonly searchControl = new FormControl('', { nonNullable: true });
  readonly results = signal<readonly AssetSearchItem[]>([]);
  readonly loading = signal(false);
  readonly searchTouched = signal(false);
  readonly lastQuery = signal('');
  readonly error = signal<ApiError | null>(null);
  readonly addingSecid = signal<string | null>(null);
  readonly existing = signal<ReadonlySet<string>>(new Set());
  readonly localAssetsWarning = signal(false);

  private readonly retry$ = new Subject<void>();
  private readonly reset$ = new Subject<void>();

  readonly hasQuery = computed(() => this.lastQuery().length > 0);
  readonly isEmptyResult = computed(
    () => this.searchTouched() && !this.loading() && !this.error() && this.results().length === 0,
  );

  readonly assetTypeLabel = assetTypeLabel;

  constructor() {
    const query$ = this.searchControl.valueChanges.pipe(
      map((value) => value.trim()),
      debounceTime(400),
    );

    merge(
      query$,
      this.retry$.pipe(map(() => this.searchControl.value.trim())),
      // Reopening the dialog cancels an in-flight search and clears the view.
      this.reset$.pipe(map(() => '')),
    )
      .pipe(
        switchMap((query) => this.runSearch(query)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((response) => {
        if (response) {
          this.results.set(response.items);
        }
      });

    effect(() => {
      if (!this.visible()) {
        return;
      }

      this.resetSearch();
      this.loadExistingAssets();
    });
  }

  isExisting(item: AssetSearchItem): boolean {
    return this.existing().has(this.key(item.secid, item.board));
  }

  retry(): void {
    this.retry$.next();
  }

  add(item: AssetSearchItem): void {
    if (this.addingSecid() !== null) {
      return;
    }

    this.addingSecid.set(item.secid);
    this.error.set(null);

    this.assets
      .create({ secid: item.secid, board: item.board })
      .pipe(
        finalize(() => this.addingSecid.set(null)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (asset) => {
          this.markExisting(asset.secid, asset.board);
          this.visible.set(false);
          this.added.emit(asset);
        },
        error: (error: unknown) => {
          const apiError = mapHttpError(error);
          this.error.set(apiError);

          if (apiError.code === 'ASSET_ALREADY_EXISTS') {
            this.markExisting(item.secid, item.board);
          }
        },
      });
  }

  private runSearch(query: string) {
    this.lastQuery.set(query);
    this.error.set(null);

    if (query.length === 0) {
      this.results.set([]);
      this.searchTouched.set(false);
      this.loading.set(false);
      return of(null);
    }

    this.searchTouched.set(true);
    this.loading.set(true);
    this.results.set([]);

    return this.assets.search(query).pipe(
      catchError((error: unknown) => {
        this.error.set(mapHttpError(error));
        return of(null);
      }),
      finalize(() => this.loading.set(false)),
    );
  }

  private loadExistingAssets(): void {
    this.assets
      .list()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.existing.set(
            new Set(response.items.map((item) => this.key(item.secid, item.board))),
          );
          this.localAssetsWarning.set(false);
        },
        error: () => {
          this.existing.set(new Set());
          this.localAssetsWarning.set(true);
        },
      });
  }

  private key(secid: string, board: string): string {
    return `${secid.trim().toUpperCase()}|${board.trim().toUpperCase()}`;
  }

  private markExisting(secid: string, board: string): void {
    const next = new Set(this.existing());
    next.add(this.key(secid, board));
    this.existing.set(next);
  }

  private resetSearch(): void {
    this.searchControl.setValue('', { emitEvent: false });
    this.results.set([]);
    this.error.set(null);
    this.searchTouched.set(false);
    this.lastQuery.set('');
    this.loading.set(false);
    this.addingSecid.set(null);
    this.reset$.next();
  }
}
