import { ChangeDetectionStrategy, Component, model, output } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter, Router } from '@angular/router';
import Aura from '@primeuix/themes/aura';
import { providePrimeNG } from 'primeng/config';
import { Subject, of, throwError } from 'rxjs';

import { ApiError } from '../../core/api/api-error';
import type { AssetDetail, PositionListResponse } from '../../core/api/models';
import { NotificationService } from '../../core/services/notification.service';
import { PositionsService } from '../../core/services/positions.service';
import { AssetSearchDialogComponent } from './asset-search-dialog/asset-search-dialog.component';
import { PortfolioPage } from './portfolio-page';

@Component({
  selector: 'app-asset-search-dialog',
  standalone: true,
  template: '',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
class AssetSearchDialogStubComponent {
  readonly visible = model(false);
  readonly added = output<AssetDetail>();
}

function makePositions(overrides: Partial<PositionListResponse> = {}): PositionListResponse {
  return {
    items: [
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
        is_stale: true,
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
    total_market_value: '16242.00',
    total_invested: '15918.45',
    ...overrides,
  };
}

const ASSET: AssetDetail = {
  id: 3,
  secid: 'GAZP',
  isin: 'RU0007661625',
  name: 'Газпром',
  short_name: 'Газпром',
  type: 'STOCK',
  board: 'TQBR',
  currency: 'RUB',
  initial_face_value: null,
  current_face_value: null,
  lot_size: 10,
  is_active: true,
  amortizations: [],
};

function normalize(value: string): string {
  return value.replace(/[\u00a0\u202f]/g, ' ');
}

describe('PortfolioPage', () => {
  let positions: jasmine.SpyObj<PositionsService>;
  let notifications: jasmine.SpyObj<NotificationService>;
  let router: Router;

  beforeEach(async () => {
    positions = jasmine.createSpyObj<PositionsService>('PositionsService', ['getPositions']);
    positions.getPositions.and.returnValue(of(makePositions()));

    notifications = jasmine.createSpyObj<NotificationService>('NotificationService', [
      'success',
      'info',
      'warn',
      'error',
    ]);

    await TestBed.configureTestingModule({
      imports: [PortfolioPage],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
        { provide: PositionsService, useValue: positions },
        { provide: NotificationService, useValue: notifications },
      ],
    })
      .overrideComponent(PortfolioPage, {
        remove: { imports: [AssetSearchDialogComponent] },
        add: { imports: [AssetSearchDialogStubComponent] },
      })
      .compileComponents();

    router = TestBed.inject(Router);
  });

  function create(): ComponentFixture<PortfolioPage> {
    const fixture = TestBed.createComponent(PortfolioPage);
    fixture.detectChanges();
    return fixture;
  }

  it('renders totals, positions and their asset links', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;
    const content = normalize(element.textContent ?? '');

    expect(positions.getPositions).toHaveBeenCalledTimes(1);
    expect(element.querySelectorAll('app-stat-card').length).toBe(3);
    expect(content).toContain('16 242,00 ₽');
    expect(content).toContain('15 918,45 ₽');
    expect(content).toContain('Акций: 1 · облигаций: 1');
    expect(element.querySelectorAll('p-table tbody tr').length).toBe(2);
    expect(content).toContain('SBER');
    expect(content).toContain('SU26238RMFS4');
    expect(content).toContain('95,123 %');
    expect(content).toContain('Устарело');

    expect(
      Array.from(element.querySelectorAll<HTMLAnchorElement>('p-table [data-position-link]')).map((link) =>
        link.getAttribute('href'),
      ),
    ).toEqual(['/assets/1', '/assets/2']);
  });

  it('filters the already loaded positions by type without refetching', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    fixture.componentInstance.onFilterChange('STOCK');
    fixture.detectChanges();
    expect(element.querySelectorAll('p-table tbody tr').length).toBe(1);
    expect(normalize(element.textContent ?? '')).toContain('SBER');
    expect(normalize(element.textContent ?? '')).not.toContain('SU26238RMFS4');

    fixture.componentInstance.onFilterChange('BOND');
    fixture.detectChanges();
    expect(element.querySelectorAll('p-table tbody tr').length).toBe(1);
    expect(normalize(element.textContent ?? '')).toContain('SU26238RMFS4');
    expect(positions.getPositions).toHaveBeenCalledTimes(1);
  });

  it('shows a filtered-empty state and resets the filter', () => {
    positions.getPositions.and.returnValue(
      of(makePositions({ items: [makePositions().items[0]], total_market_value: '4530.00' })),
    );

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    fixture.componentInstance.onFilterChange('BOND');
    fixture.detectChanges();

    expect(normalize(element.textContent ?? '')).toContain('По выбранному типу открытых позиций нет');

    element.querySelector<HTMLButtonElement>('.portfolio__filter-empty button')?.click();
    fixture.detectChanges();

    expect(fixture.componentInstance.filter()).toBe('ALL');
    expect(element.querySelectorAll('p-table tbody tr').length).toBe(1);
  });

  it('shows an empty state with asset search and a CTA', () => {
    positions.getPositions.and.returnValue(
      of({ items: [], total_market_value: '0.00', total_invested: '0.00' }),
    );

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    expect(normalize(element.textContent ?? '')).toContain(
      'В портфеле пока нет открытых позиций',
    );
    expect(element.querySelector('p-table')).toBeNull();

    fixture.componentInstance.openAssetSearch();
    fixture.detectChanges();

    expect(fixture.componentInstance.assetSearchVisible()).toBeTrue();
  });

  it('shows an error state and retries', () => {
    positions.getPositions.and.returnValues(
      throwError(() => new ApiError(0, 'NETWORK_ERROR', 'Нет связи с backend')),
      of(makePositions()),
    );

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    expect(normalize(element.textContent ?? '')).toContain('Нет связи с backend');

    element.querySelector<HTMLButtonElement>('app-error-state button')?.click();
    fixture.detectChanges();

    expect(positions.getPositions).toHaveBeenCalledTimes(2);
    expect(element.querySelector('app-error-state')).toBeNull();
    expect(element.querySelectorAll('p-table tbody tr').length).toBe(2);
  });

  it('shows a skeleton while the first response is pending', () => {
    const pending = new Subject<PositionListResponse>();
    positions.getPositions.and.returnValue(pending.asObservable());

    const fixture = TestBed.createComponent(PortfolioPage);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('app-loading-skeleton')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('p-table')).toBeNull();

    pending.next(makePositions());
    pending.complete();
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('app-loading-skeleton')).toBeNull();
    expect(fixture.nativeElement.querySelectorAll('p-table tbody tr').length).toBe(2);
  });

  it('navigates to the new asset card and shows a toast after adding', () => {
    const navigate = spyOn(router, 'navigate').and.resolveTo(true);
    const fixture = create();

    fixture.componentInstance.onAssetAdded(ASSET);

    expect(notifications.success).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith(['/assets', 3]);
  });
});
