import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

import type { Period } from '../../../core/api/models';

interface PeriodOption {
  value: Period;
  label: string;
}

/** Dashboard/period selector: 1M / 3M / 1Y / ALL. */
@Component({
  selector: 'app-period-switcher',
  standalone: true,
  templateUrl: './period-switcher.component.html',
  styleUrl: './period-switcher.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PeriodSwitcherComponent {
  readonly selected = input<Period>('1Y');
  readonly change = output<Period>();

  readonly options: readonly PeriodOption[] = [
    { value: '1M', label: '1 мес.' },
    { value: '3M', label: '3 мес.' },
    { value: '1Y', label: '1 год' },
    { value: 'ALL', label: 'Все' },
  ];

  select(period: Period): void {
    if (period !== this.selected()) {
      this.change.emit(period);
    }
  }
}
