import type { DashboardSeriesPointOut } from '../../../core/api/models';
import {
  buildChartAriaLabel,
  buildValueChartData,
  buildValueChartOptions,
  formatChartDate,
} from './value-chart.component';

function point(index: number): DashboardSeriesPointOut {
  const day = String((index % 28) + 1).padStart(2, '0');
  return {
    date: `2026-05-${day}`,
    market_value: String(2500 + index),
    invested: String(1000 + index),
    is_partial: false,
  };
}

describe('ValueChart builders', () => {
  it('formats API dates as dd.MM.yy without timezone math', () => {
    expect(formatChartDate('2026-05-03')).toBe('03.05.26');
    expect(formatChartDate('2026-10-30')).toBe('30.10.26');
    expect(formatChartDate('not-a-date')).toBe('not-a-date');
  });

  it('maps the series to two labelled datasets', () => {
    const data = buildValueChartData([
      { date: '2026-05-03', market_value: '16242.00', invested: '15918.45', is_partial: false },
      { date: '2026-05-04', market_value: '16300.00', invested: '15918.45', is_partial: true },
    ]);

    expect(data.datasets.map((dataset) => dataset.label)).toEqual(['Стоимость', 'Вложено']);
    expect(data.datasets[0].data).toEqual([16242, 16300]);
    expect(data.datasets[1].data).toEqual([15918.45, 15918.45]);
    expect(data.labels).toEqual(['03.05.26', '04.05.26']);
    expect(data.datasets[0].tension).toBe(0);
    expect(data.datasets[1].tension).toBe(0);
  });

  it('preserves every point without aggregation or interpolation', () => {
    const series = Array.from({ length: 181 }, (_, index) => point(index));
    const data = buildValueChartData(series);

    expect(data.labels?.length).toBe(181);
    expect(data.datasets[0].data.length).toBe(181);
    expect(data.datasets[1].data.length).toBe(181);
  });

  it('builds responsive options with a bottom legend and tooltip callbacks', () => {
    const options = buildValueChartOptions();

    expect(options.responsive).toBeTrue();
    expect(options.maintainAspectRatio).toBeFalse();
    expect(options.plugins?.legend?.position).toBe('bottom');
    expect(options.plugins?.tooltip?.mode).toBe('index');
    expect(options.plugins?.tooltip?.callbacks?.label).toBeDefined();
    expect(options.scales?.['y']).toBeDefined();
  });

  it('describes the series for screen readers', () => {
    const label = buildChartAriaLabel([
      { date: '2026-05-03', market_value: '16242.00', invested: '15918.45', is_partial: false },
      { date: '2026-10-30', market_value: '17000.00', invested: '15918.45', is_partial: false },
    ]).replace(/[\u00a0\u202f]/g, ' ');

    expect(label).toContain('с 03.05.26 по 30.10.26');
    expect(label).toContain('17 000,00 ₽');
    expect(label).toContain('15 918,45 ₽');
    expect(label).toContain('Точек: 2');

    expect(buildChartAriaLabel([])).toContain('нет данных');
  });
});
