import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';

import type { PositionItem } from '../../../core/api/models';
import { toPriceSource } from '../../../core/api/models';
import { assetTypeLabel } from '../../../core/formatting/labels';
import { MoneyPipe } from '../../../core/formatting/money.pipe';
import { PricePipe } from '../../../core/formatting/price.pipe';
import { SharePipe } from '../../../core/formatting/share.pipe';
import { PriceSourceBadgeComponent } from '../price-source-badge/price-source-badge.component';

/** Reusable open-positions table for the dashboard and the portfolio page. */
@Component({
  selector: 'app-positions-table',
  standalone: true,
  imports: [
    RouterLink,
    TableModule,
    TagModule,
    MoneyPipe,
    PricePipe,
    SharePipe,
    PriceSourceBadgeComponent,
  ],
  templateUrl: './positions-table.component.html',
  styleUrl: './positions-table.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PositionsTableComponent {
  readonly positions = input.required<PositionItem[]>();

  readonly assetTypeLabel = assetTypeLabel;
  readonly toPriceSource = toPriceSource;
}
