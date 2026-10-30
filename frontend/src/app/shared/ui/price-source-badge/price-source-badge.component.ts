import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TagModule } from 'primeng/tag';

import { DatePipe } from '../../../core/formatting/date.pipe';
import type { PriceSource } from '../../../core/api/models';

type TagSeverity = 'success' | 'info' | 'warn' | 'danger' | 'secondary' | 'contrast';

interface SourcePresentation {
  label: string;
  severity: TagSeverity;
  icon: string;
}

/** Badge describing where a position price came from and whether it is stale. */
@Component({
  selector: 'app-price-source-badge',
  standalone: true,
  imports: [TagModule, DatePipe],
  templateUrl: './price-source-badge.component.html',
  styleUrl: './price-source-badge.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PriceSourceBadgeComponent {
  readonly source = input<PriceSource | ''>('');
  readonly isStale = input<boolean>(false);
  readonly priceDate = input<string | null>(null);

  readonly presentation = computed<SourcePresentation>(() => {
    switch (this.source()) {
      case 'MOEX':
        return { label: 'MOEX', severity: 'success', icon: 'pi pi-check' };
      case 'MANUAL':
        return { label: 'Вручную', severity: 'info', icon: 'pi pi-pencil' };
      case 'COST':
        return { label: 'Себестоимость', severity: 'danger', icon: 'pi pi-exclamation-triangle' };
      default:
        return { label: this.source() || 'Нет данных', severity: 'secondary', icon: 'pi pi-question' };
    }
  });
}
