import {
  ChangeDetectionStrategy,
  Component,
  input,
  model,
  output,
} from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter, Router } from '@angular/router';
import Aura from '@primeuix/themes/aura';
import { ConfirmationService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';
import { of, throwError } from 'rxjs';

import { ApiError } from '../../core/api/api-error';
import type {
  AssetDetail,
  IncomeItem,
  OperationResponse,
  PositionListResponse,
  QuoteItem,
} from '../../core/api/models';
import { AssetsService } from '../../core/services/assets.service';
import { IncomeService } from '../../core/services/income.service';
import { NotificationService } from '../../core/services/notification.service';
import { OperationsService } from '../../core/services/operations.service';
import { PositionsService } from '../../core/services/positions.service';
import { QuotesService } from '../../core/services/quotes.service';
import { AssetDetailPage } from './asset-detail-page';
import { OperationDialogComponent } from './operation-dialog/operation-dialog.component';

@Component({
  selector: 'app-operation-dialog',
  standalone: true,
  template: '',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
class OperationDialogStubComponent {
  readonly visible = model(false);
  readonly asset = input.required<AssetDetail>();
  readonly operation = input<OperationResponse | null>(null);
  readonly saved = output<void>();
}

const ASSET: AssetDetail = {
  id: 1,
  secid: 'SBER',
  isin: 'RU0009029540',
  name: 'Сбербанк',
  short_name: 'Сбербанк',
  type: 'STOCK',
  board: 'TQBR',
  currency: 'RUB',
  initial_face_value: null,
  current_face_value: null,
  lot_size: 10,
  is_active: true,
  amortizations: [],
};

const POSITIONS: PositionListResponse = {
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
  ],
  total_market_value: '4530.00',
  total_invested: '1650.00',
};

const OPERATION: OperationResponse = {
  id: 1,
  asset_id: 1,
  type: 'BUY',
  trade_date: '2026-05-03',
  quantity: 10,
  input_price: '100.000000',
  input_price_type: 'RUB',
  price_rub: '100.000000',
  note: 'Первая покупка',
};

const INCOMES: IncomeItem[] = [
  {
    id: 1,
    asset_id: 1,
    asset_secid: 'SBER',
    kind: 'DIVIDEND',
    status: 'PAID',
    amount_per_unit: '13.33',
    quantity: 15,
    amount_total: '200.00',
    currency: 'RUB',
    record_date: null,
    pay_date: '2026-07-20',
    source: 'MANUAL',
    note: null,
    is_overdue: false,
  },
  {
    id: 2,
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
];

const QUOTES: QuoteItem[] = [
  {
    id: 1,
    asset_id: 1,
    quote_date: '2026-10-29',
    price: '300.000000',
    price_type: 'RUB',
    source: 'MOEX',
    fetched_at: '2026-10-29T16:05:00Z',
  },
  {
    id: 2,
    asset_id: 1,
    quote_date: '2026-10-30',
    price: '302.000000',
    price_type: 'RUB',
    source: 'MANUAL',
    fetched_at: '2026-10-30T16:05:00Z',
  },
];

const TOTALS = {
  dividends_paid: '200.00',
  coupons_paid: '0.00',
  expected_coupons: '525.00',
};

function normalize(value: string): string {
  return value.replace(/[\u00a0\u202f]/g, ' ');
}

describe('AssetDetailPage', () => {
  let assets: jasmine.SpyObj<AssetsService>;
  let positions: jasmine.SpyObj<PositionsService>;
  let operations: jasmine.SpyObj<OperationsService>;
  let incomes: jasmine.SpyObj<IncomeService>;
  let quotes: jasmine.SpyObj<QuotesService>;
  let notifications: jasmine.SpyObj<NotificationService>;
  let confirmation: { confirm: jasmine.Spy };
  let router: Router;

  beforeEach(async () => {
    assets = jasmine.createSpyObj<AssetsService>('AssetsService', [
      'list',
      'search',
      'create',
      'get',
      'refresh',
      'remove',
    ]);
    assets.get.and.returnValue(of(ASSET));
    assets.refresh.and.returnValue(of({ ...ASSET, name: 'Сбербанк (обновлён)' }));
    assets.remove.and.returnValue(of(undefined));

    positions = jasmine.createSpyObj<PositionsService>('PositionsService', ['getPositions']);
    positions.getPositions.and.returnValue(of(POSITIONS));

    operations = jasmine.createSpyObj<OperationsService>('OperationsService', [
      'list',
      'create',
      'update',
      'remove',
    ]);
    operations.list.and.returnValue(of({ items: [OPERATION] }));
    operations.remove.and.returnValue(of(undefined));

    incomes = jasmine.createSpyObj<IncomeService>('IncomeService', [
      'list',
      'create',
      'update',
      'markPaid',
      'remove',
    ]);
    incomes.list.and.returnValue(of({ items: INCOMES, totals: TOTALS }));

    quotes = jasmine.createSpyObj<QuotesService>('QuotesService', [
      'history',
      'refreshAll',
      'addManual',
    ]);
    quotes.history.and.callFake((_assetId: number, period = '1Y') =>
      of({ asset_id: 1, period, items: QUOTES }),
    );

    notifications = jasmine.createSpyObj<NotificationService>('NotificationService', [
      'success',
      'info',
      'warn',
      'error',
    ]);
    confirmation = { confirm: jasmine.createSpy('confirm') };

    await TestBed.configureTestingModule({
      imports: [AssetDetailPage],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
        { provide: AssetsService, useValue: assets },
        { provide: PositionsService, useValue: positions },
        { provide: OperationsService, useValue: operations },
        { provide: IncomeService, useValue: incomes },
        { provide: QuotesService, useValue: quotes },
        { provide: NotificationService, useValue: notifications },
        { provide: ConfirmationService, useValue: confirmation },
      ],
    })
      .overrideComponent(AssetDetailPage, {
        remove: { imports: [OperationDialogComponent] },
        add: { imports: [OperationDialogStubComponent] },
      })
      .compileComponents();

    router = TestBed.inject(Router);
  });

  function create(assetId = '1'): ComponentFixture<AssetDetailPage> {
    const fixture = TestBed.createComponent(AssetDetailPage);
    fixture.componentRef.setInput('assetId', assetId);
    fixture.detectChanges();
    return fixture;
  }

  it('loads the asset, position, operations, incomes and quote history', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;
    const content = normalize(element.textContent ?? '');

    expect(assets.get).toHaveBeenCalledWith(1);
    expect(positions.getPositions).toHaveBeenCalled();
    expect(operations.list).toHaveBeenCalledWith({ assetId: 1 });
    expect(incomes.list).toHaveBeenCalledWith({ assetId: 1 });
    expect(quotes.history).toHaveBeenCalledWith(1, '1Y');

    expect(content).toContain('SBER · Сбербанк');
    expect(content).toContain('Сбербанк');
    expect(content).toContain('Акция');
    expect(content).toContain('15');
    expect(content).toContain('110,00 ₽');
    expect(content).toContain('302,00 ₽');
    expect(content).toContain('4 530,00 ₽');
    expect(content).toContain('27,89 %');
    expect(content).toContain('Первая покупка');
    expect(content).toContain('Дивиденд');
    expect(content).toContain('Купон');
    expect(content).toContain('525,00 ₽');
    expect(content).toContain('300,00 ₽');
    expect(element.querySelectorAll('app-stat-card').length).toBe(5);
  });

  it('shows a no-position state with an add-operation CTA', () => {
    positions.getPositions.and.returnValue(
      of({ items: [], total_market_value: '0.00', total_invested: '0.00' }),
    );

    const fixture = create();

    expect(normalize(fixture.nativeElement.textContent)).toContain('Нет открытой позиции');
  });

  it('shows an error state and retries the initial load', () => {
    assets.get.and.returnValues(
      throwError(() => new ApiError(404, 'ASSET_NOT_FOUND', 'Актив 1 не найден')),
      of(ASSET),
    );

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    expect(normalize(element.textContent ?? '')).toContain('Актив 1 не найден');

    element.querySelector<HTMLButtonElement>('app-error-state button')?.click();
    fixture.detectChanges();

    expect(assets.get).toHaveBeenCalledTimes(2);
    expect(element.querySelector('app-error-state')).toBeNull();
    expect(normalize(element.textContent ?? '')).toContain('SBER');
  });

  it('opens the operation dialog in create and edit modes', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.openCreateOperation();
    expect(component.operationDialogVisible()).toBeTrue();
    expect(component.editingOperation()).toBeNull();

    component.openEditOperation(OPERATION);
    expect(component.operationDialogVisible()).toBeTrue();
    expect(component.editingOperation()).toBe(OPERATION);
  });

  it('reloads operations and positions after the dialog saves', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    operations.list.calls.reset();
    positions.getPositions.calls.reset();

    component.onOperationSaved();

    expect(operations.list).toHaveBeenCalledWith({ assetId: 1 });
    expect(positions.getPositions).toHaveBeenCalled();
  });

  it('confirms and deletes an operation, then reloads', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.deleteOperation(OPERATION);

    expect(confirmation.confirm).toHaveBeenCalled();
    const options = confirmation.confirm.calls.mostRecent().args[0] as {
      message: string;
      accept: () => void;
    };
    expect(options.message).toContain('backend отклонит операцию');

    options.accept();

    expect(operations.remove).toHaveBeenCalledWith(1);
    expect(notifications.success).toHaveBeenCalledWith('Операция удалена');
  });

  it('confirms asset deletion and navigates back to the portfolio', () => {
    const navigate = spyOn(router, 'navigate').and.resolveTo(true);
    const fixture = create();
    const component = fixture.componentInstance;

    component.confirmDeleteAsset();
    const options = confirmation.confirm.calls.mostRecent().args[0] as { accept: () => void };
    options.accept();

    expect(assets.remove).toHaveBeenCalledWith(1);
    expect(navigate).toHaveBeenCalledWith(['/portfolio']);
  });

  it('keeps the asset and shows a toast when deletion is blocked by 409', () => {
    assets.remove.and.returnValue(
      throwError(
        () =>
          new ApiError(409, 'ASSET_IN_USE', 'Нельзя удалить актив, по которому есть операции'),
      ),
    );
    const navigate = spyOn(router, 'navigate').and.resolveTo(true);
    const fixture = create();
    const component = fixture.componentInstance;

    component.confirmDeleteAsset();
    const options = confirmation.confirm.calls.mostRecent().args[0] as { accept: () => void };
    options.accept();

    expect(notifications.error).toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });

  it('refreshes asset metadata and reloads the dependent data', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.refreshAsset();

    expect(assets.refresh).toHaveBeenCalledWith(1);
    expect(component.asset()?.name).toBe('Сбербанк (обновлён)');
    expect(notifications.success).toHaveBeenCalled();
  });

  it('reloads the quote history when the period changes', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.onQuotePeriodChange('3M');

    expect(component.quotePeriod()).toBe('3M');
    expect(quotes.history).toHaveBeenCalledWith(1, '3M');
    expect(component.quotes().length).toBe(2);
  });
});
