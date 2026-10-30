import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export type StatCardSeverity = 'neutral' | 'success' | 'info' | 'warn' | 'danger';

/** Presentational KPI card. Values are pre-formatted by the caller. */
@Component({
  selector: 'app-stat-card',
  standalone: true,
  templateUrl: './stat-card.component.html',
  styleUrl: './stat-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatCardComponent {
  readonly label = input.required<string>();
  readonly value = input.required<string>();
  readonly icon = input<string>('');
  readonly hint = input<string>('');
  readonly severity = input<StatCardSeverity>('neutral');
}
