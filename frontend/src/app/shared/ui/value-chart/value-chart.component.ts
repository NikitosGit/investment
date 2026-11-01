import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import type { ChartData, ChartOptions, TooltipItem } from 'chart.js';
import { ChartModule } from 'primeng/chart';

import type { DashboardSeriesPointOut } from '../../../core/api/models';

const MARKET_COLOR = '#0f766e';
const INVESTED_COLOR = '#64748b';
const GRID_COLOR = '#e2e8f0';

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

const RUB = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const COMPACT = new Intl.NumberFormat('ru-RU', {
  notation: 'compact',
  maximumFractionDigits: 1,
});

/** `YYYY-MM-DD` -> `dd.MM.yy` without timezone math. */
export function formatChartDate(value: string): string {
  const match = DATE_ONLY.exec(value.trim());
  return match ? `${match[3]}.${match[2]}.${match[1].slice(2)}` : value;
}

/** Tooltip/y-axis money formatting. Display only. */
export function formatChartMoney(value: number): string {
  return RUB.format(value);
}

/** Compact ruble label for the value axis. */
export function formatCompactRub(value: number): string {
  return `${COMPACT.format(value)} ₽`;
}

/**
 * Map the API series to a two-line Chart.js dataset.
 *
 * Only labels are reformatted and money strings become numbers for display;
 * points are never aggregated, interpolated or dropped.
 */
export function buildValueChartData(
  series: readonly DashboardSeriesPointOut[],
): ChartData<'line'> {
  return {
    labels: series.map((point) => formatChartDate(point.date)),
    datasets: [
      {
        label: 'Стоимость',
        data: series.map((point) => Number(point.market_value)),
        borderColor: MARKET_COLOR,
        backgroundColor: 'rgba(15, 118, 110, 0.12)',
        pointBackgroundColor: MARKET_COLOR,
        pointRadius: 0,
        borderWidth: 2,
        tension: 0,
        fill: true,
      },
      {
        label: 'Вложено',
        data: series.map((point) => Number(point.invested)),
        borderColor: INVESTED_COLOR,
        backgroundColor: 'rgba(100, 116, 139, 0.08)',
        pointBackgroundColor: INVESTED_COLOR,
        pointRadius: 0,
        borderWidth: 2,
        borderDash: [5, 4],
        tension: 0,
        fill: false,
      },
    ],
  };
}

/** Chart options for the portfolio value chart. */
export function buildValueChartOptions(): ChartOptions<'line'> {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          usePointStyle: true,
          boxWidth: 8,
          padding: 16,
        },
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        callbacks: {
          label: (context: TooltipItem<'line'>) =>
            `${context.dataset.label ?? ''}: ${formatChartMoney(context.parsed.y)}`,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          autoSkip: true,
          autoSkipPadding: 16,
          maxRotation: 0,
        },
      },
      y: {
        beginAtZero: false,
        grid: { color: GRID_COLOR },
        ticks: {
          callback: (value) => formatCompactRub(Number(value)),
        },
      },
    },
  };
}

/** Line chart of portfolio value versus invested capital. */
@Component({
  selector: 'app-value-chart',
  standalone: true,
  imports: [ChartModule],
  templateUrl: './value-chart.component.html',
  styleUrl: './value-chart.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ValueChartComponent {
  readonly series = input.required<readonly DashboardSeriesPointOut[]>();
  readonly height = input<string>('320px');

  readonly chartData = computed(() => buildValueChartData(this.series()));
  readonly chartOptions = buildValueChartOptions();
}
