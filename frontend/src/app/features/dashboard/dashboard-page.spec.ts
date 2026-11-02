import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import Aura from '@primeuix/themes/aura';
import { MessageService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';
import { Subject, of, throwError } from 'rxjs';

import { ApiError } from '../../core/api/api-error';
import type {
  DashboardResponse,
  DashboardSeriesPointOut,
  Period,
} from '../../core/api/models';
import { DashboardService } from '../../core/services/dashboard.service';
import { NotificationService } from '../../core/services/notification.service';
import { ValueChartComponent } from '../../shared/ui/value-chart/value-chart.component';
import { DashboardPage } from './dashboard-page';

@Component({
  selector: 'app-value-chart',
  standalone: true,
  template: '<div class="value-chart-stub">{{ series().length }} точек</div>',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
class ValueChartStubComponent {
  readonly series = input.required<readonly DashboardSeriesPointOut[]>();
  readonly height = input<string>();
}

function makeDashboard(overrides: Partial<DashboardResponse> = {}): DashboardResponse {
  return {
    as_of: '2026-10-30',
    currency: 'RUB',
    period: '1Y',
    totals: {
      market_value: '16242.00',
      invested: '15918.45',
      dividends_paid: '200.00',
      coupons_paid: '525.00',
      income_paid_total: '725.00',
      expected_coupons: '1575.00',
      positions_count: 2,
      assets_count: 2,
    },
    series: [
      { date: '2026-05-03', market_value: '2500.00', invested: '1000.00', is_partial: false },
      { date: '2026-08-01', market_value: '12000.00', invested: '9000.00', is_partial: false },
      { date: '2026-10-30', market_value: '16242.00', invested: '15918.45', is_partial: false },
    ],
    positions: [
      {
        asset: { id: 1, secid: 'SBER', name: 'Сбербанк', type: 'STOCK' },
        quantity: 15,
        avg_price: '110.000000',
        avg_price_percent: null,
        current_price: '302.000000',
        current_price_type: 'RUB',
        current_face_value: null,
        market_value: '4530.00',
        invested: '1650.00',
        share: '0.2789',
        price_date: '2026-10-30',
        price_source: 'MANUAL',
        is_stale: false,
      },
      {
        asset: { id: 2, secid: 'SU26238RMFS4', name: 'ОФЗ 26238', type: 'BOND' },
        quantity: 15,
        avg_price: '951.230000',
        avg_price_percent: '95.123000',
        current_price: '97.600000',
        current_price_type: 'PERCENT',
        current_face_value: '800.00',
        market_value: '11712.00',
        invested: '14268.45',
        share: '0.7211',
        price_date: '2026-10-30',
        price_source: 'MANUAL',
        is_stale: false,
      },
    ],
    upcoming_coupons: [
      {
        id: 3,
        asset_id: 2,
        asset_secid: 'SU26238RMFS4',
        kind: 'COUPON',
        status: 'EXPECTED',
        amount_per_unit: '35.00',
        quantity: 15,
        amount_total: '525.00',
        currency: 'RUB',
        record_date: null,
        pay_date: '2026-11-09',
        source: 'MANUAL',
        note: null,
        is_overdue: false,
      },
      {
        id: 4,
        asset_id: 2,
        asset_secid: 'SU26238RMFS4',
        kind: 'COUPON',
        status: 'EXPECTED',
        amount_per_unit: '35.00',
        quantity: 15,
        amount_total: '525.00',
        currency: 'RUB',
        record_date: null,
        pay_date: '2027-02-07',
        source: 'MANUAL',
        note: null,
        is_overdue: false,
      },
      {
        id: 5,
        asset_id: 2,
        asset_secid: 'SU26238RMFS4',
        kind: 'COUPON',
        status: 'EXPECTED',
        amount_per_unit: '35.00',
        quantity: 15,
        amount_total: '525.00',
        currency: 'RUB',
        record_date: null,
        pay_date: '2027-05-08',
        source: 'MANUAL',
        note: null,
        is_overdue: false,
      },
    ],
    is_partial: false,
    ...overrides,
  };
}

function normalize(value: string): string {
  return value.replace(/[\u00a0\u202f]/g, ' ');
}

function textOf(element: HTMLElement): string {
  return normalize(element.textContent ?? '');
}

describe('DashboardPage', () => {
  let dashboard: jasmine.SpyObj<DashboardService>;
  let notifications: jasmine.SpyObj<NotificationService>;

  beforeEach(async () => {
    dashboard = jasmine.createSpyObj<DashboardService>('DashboardService', ['getDashboard']);
    dashboard.getDashboard.and.returnValue(of(makeDashboard()));

    notifications = jasmine.createSpyObj<NotificationService>('NotificationService', [
      'success',
      'info',
      'warn',
      'error',
    ]);

    await TestBed.configureTestingModule({
      imports: [DashboardPage],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
        MessageService,
        { provide: DashboardService, useValue: dashboard },
        { provide: NotificationService, useValue: notifications },
      ],
    })
      .overrideComponent(DashboardPage, {
        remove: { imports: [ValueChartComponent] },
        add: { imports: [ValueChartStubComponent] },
      })
      .compileComponents();
  });

  function create(): ComponentFixture<DashboardPage> {
    const fixture = TestBed.createComponent(DashboardPage);
    fixture.detectChanges();
    return fixture;
  }

  it('loads without a period and renders five cards, positions and coupons', () => {
    const fixture = create();

    expect(dashboard.getDashboard).toHaveBeenCalledTimes(1);
    expect(dashboard.getDashboard.calls.first().args.length).toBe(0);

    const element = fixture.nativeElement as HTMLElement;
    const content = textOf(element);

    expect(element.querySelectorAll('app-stat-card').length).toBe(5);
    expect(content).toContain('16 242,00 ₽');
    expect(content).toContain('15 918,45 ₽');
    expect(content).toContain('200,00 ₽');
    expect(content).toContain('525,00 ₽');
    expect(content).toContain('1 575,00 ₽');

    expect(element.querySelectorAll('p-table tbody tr').length).toBe(2);
    expect(content).toContain('SBER');
    expect(content).toContain('SU26238RMFS4');
    expect(content).toContain('95,123 %');
    expect(content).toContain('27,89 %');
    expect(content).toContain('72,11 %');

    expect(element.querySelectorAll('.dashboard-coupons tbody tr').length).toBe(3);
    expect(content).toContain('09.11.2026');
    expect(element.querySelector('.value-chart-stub')?.textContent).toContain('3 точек');
  });

  it('links positions and coupons to their routes', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    const assetLinks = Array.from(
      element.querySelectorAll<HTMLAnchorElement>('p-table [data-position-link]'),
    ).map((link) => link.getAttribute('href'));

    expect(assetLinks).toEqual(['/assets/1', '/assets/2']);
    expect(
      element.querySelector<HTMLAnchorElement>('.dashboard-coupons a')?.getAttribute('href'),
    ).toBe('/assets/2');
    expect(
      Array.from(element.querySelectorAll<HTMLAnchorElement>('.dashboard__link')).map((link) =>
        link.getAttribute('href'),
      ),
    ).toContain('/income');
  });

  it('gives the coupons table an accessible name', () => {
    const fixture = create();
    const table = fixture.nativeElement.querySelector(
      '.dashboard-coupons',
    ) as HTMLTableElement;

    expect(table.getAttribute('aria-label')).toBe('Ближайшие купоны');
  });

  it('requests the selected period without changing totals', () => {
    dashboard.getDashboard.and.callFake((period?: Period) =>
      of(
        period === '3M'
          ? {
              ...makeDashboard({ period: '3M' }),
              series: [
                {
                  date: '2026-10-30',
                  market_value: '16242.00',
                  invested: '15918.45',
                  is_partial: false,
                },
              ],
            }
          : makeDashboard(),
      ),
    );

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;
    const threeMonths = Array.from(
      element.querySelectorAll<HTMLButtonElement>('app-period-switcher button'),
    ).find((button) => button.textContent?.trim() === '3 мес.');

    threeMonths?.click();
    fixture.detectChanges();

    expect(dashboard.getDashboard).toHaveBeenCalledWith('3M');
    expect(fixture.componentInstance.selectedPeriod()).toBe('3M');
    expect(fixture.componentInstance.data()?.totals.market_value).toBe('16242.00');
    expect(element.querySelector('.value-chart-stub')?.textContent).toContain('1 точек');
  });

  it('keeps the current period when the backend resolves an unknown one', () => {
    dashboard.getDashboard.and.returnValue(of(makeDashboard({ period: '2Y' })));

    const fixture = create();

    expect(fixture.componentInstance.selectedPeriod()).toBe('1Y');
    expect(textOf(fixture.nativeElement as HTMLElement)).toContain('Период: 1 год');
  });

  it('ignores a late response from a superseded period', () => {
    const threeMonths = new Subject<DashboardResponse>();
    const oneYear = new Subject<DashboardResponse>();

    dashboard.getDashboard.and.returnValues(
      of(makeDashboard()),
      threeMonths.asObservable(),
      oneYear.asObservable(),
    );

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;
    const button = (label: string): HTMLButtonElement | undefined =>
      Array.from(element.querySelectorAll<HTMLButtonElement>('app-period-switcher button')).find(
        (candidate) => candidate.textContent?.trim() === label,
      );

    button('3 мес.')?.click();
    fixture.detectChanges();
    button('1 год')?.click();
    fixture.detectChanges();

    oneYear.next({
      ...makeDashboard({ period: '1Y' }),
      series: [
        { date: '2026-09-01', market_value: '100.00', invested: '90.00', is_partial: false },
        { date: '2026-10-30', market_value: '200.00', invested: '90.00', is_partial: false },
      ],
    });
    oneYear.complete();
    fixture.detectChanges();

    threeMonths.next({
      ...makeDashboard({ period: '3M' }),
      series: [
        { date: '2026-08-01', market_value: '1.00', invested: '1.00', is_partial: false },
        { date: '2026-09-01', market_value: '2.00', invested: '1.00', is_partial: false },
        { date: '2026-10-01', market_value: '3.00', invested: '1.00', is_partial: false },
      ],
    });
    threeMonths.complete();
    fixture.detectChanges();

    expect(fixture.componentInstance.selectedPeriod()).toBe('1Y');
    expect(fixture.componentInstance.data()?.period).toBe('1Y');
    expect(element.querySelector('.value-chart-stub')?.textContent).toContain('2 точек');
  });

  it('shows the partial warning and stale price badge', () => {
    const data = makeDashboard({ is_partial: true });
    data.positions[0].is_stale = true;
    dashboard.getDashboard.and.returnValue(of(data));

    const fixture = create();
    const content = textOf(fixture.nativeElement as HTMLElement);

    expect(content).toContain('Часть графика оценена по себестоимости');
    expect(content).toContain('Устарело');
    expect(content).toContain('цена от 30.10.2026');
  });

  it('shows an empty state with a portfolio CTA for an empty portfolio', () => {
    const data = makeDashboard({ positions: [], upcoming_coupons: [], series: [] });
    data.totals.assets_count = 0;
    data.totals.positions_count = 0;
    dashboard.getDashboard.and.returnValue(of(data));

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    expect(textOf(element)).toContain('Портфель пуст');
    expect(element.querySelector('app-empty-state a')?.getAttribute('href')).toBe('/portfolio');
    expect(element.querySelector('p-table')).toBeNull();
  });

  it('explains that assets exist but there are no open positions', () => {
    const data = makeDashboard({ positions: [], upcoming_coupons: [], series: [] });
    data.totals.assets_count = 2;
    data.totals.positions_count = 0;
    dashboard.getDashboard.and.returnValue(of(data));

    const fixture = create();
    const content = textOf(fixture.nativeElement as HTMLElement);

    expect(content).toContain('Нет открытых позиций');
    expect(content).toContain('Активы добавлены, но операций пока нет');
    expect(content).not.toContain('Портфель пуст');
  });

  it('shows an error state on the initial failure and retries', () => {
    dashboard.getDashboard.and.returnValues(
      throwError(() => new ApiError(0, 'NETWORK_ERROR', 'Нет связи с сервером')),
      of(makeDashboard()),
    );

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    expect(textOf(element)).toContain('Нет связи с сервером');

    element.querySelector<HTMLButtonElement>('app-error-state button')?.click();
    fixture.detectChanges();

    expect(dashboard.getDashboard).toHaveBeenCalledTimes(2);
    expect(element.querySelector('app-error-state')).toBeNull();
    expect(element.querySelectorAll('app-stat-card').length).toBe(5);
  });

  it('shows a skeleton while the first response is pending', () => {
    const pending = new Subject<DashboardResponse>();
    dashboard.getDashboard.and.returnValue(pending.asObservable());

    const fixture = TestBed.createComponent(DashboardPage);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('app-loading-skeleton')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('app-stat-card')).toBeNull();

    pending.next(makeDashboard());
    pending.complete();
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('app-loading-skeleton')).toBeNull();
    expect(fixture.nativeElement.querySelectorAll('app-stat-card').length).toBe(5);
  });

  it('keeps the last good data and shows a toast when a refresh fails', () => {
    dashboard.getDashboard.and.returnValues(
      of(makeDashboard()),
      throwError(() => new ApiError(0, 'NETWORK_ERROR', 'Нет связи с сервером')),
    );

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;
    const threeMonths = Array.from(
      element.querySelectorAll<HTMLButtonElement>('app-period-switcher button'),
    ).find((button) => button.textContent?.trim() === '3 мес.');

    threeMonths?.click();
    fixture.detectChanges();

    expect(notifications.error).toHaveBeenCalled();
    expect(textOf(element)).toContain('16 242,00 ₽');
    expect(element.querySelector('app-error-state')).toBeNull();
    expect(fixture.componentInstance.selectedPeriod()).toBe('1Y');
  });
});
