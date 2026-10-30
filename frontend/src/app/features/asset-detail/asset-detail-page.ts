import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { EmptyStateComponent } from '../../shared/ui/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/ui/page-header/page-header.component';

@Component({
  selector: 'app-asset-detail-page',
  standalone: true,
  imports: [PageHeaderComponent, EmptyStateComponent],
  templateUrl: './asset-detail-page.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AssetDetailPage {
  /** Bound from the `assets/:assetId` route via `withComponentInputBinding()`. */
  readonly assetId = input<string>();

  readonly subtitle = computed(() => {
    const id = this.assetId();
    return id ? `Актив #${id}: позиция, операции и история цен.` : 'Позиция, операции и история цен.';
  });
}
