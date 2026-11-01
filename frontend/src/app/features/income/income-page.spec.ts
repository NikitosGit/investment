import { ChangeDetectionStrategy, Component, input, model, output } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import Aura from '@primeuix/themes/aura';
import { ConfirmationService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';
import { Subject, of, throwError } from 'rxjs';

import { ApiError } from '../../core/api/api-error';
import type {
  AssetListItem,
  IncomeItem,
  IncomeListResponse,
} from '../../core/api/models';
import { AssetsService } from '../../core/services/assets.service';
import { IncomeService } from '../../core/services/income.service';
import { NotificationService } from '../../core/services/notification.service';
import { IncomeFormDialogComponent } from './income-form-dialog/income-form-dialog.component';
import { IncomePage } from './income-page';
import { MarkPaidDialogComponent } from './mark-paid-dialog/mark-paid-dialog.component';

@Component({
  selector: 'app-income-form-dialog',
  standalone: true,
  template: '',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
class IncomeFormDialogStubComponent {
  readonly visible = model(false);
  readonly income = input<IncomeItem | null>(null);
  readonly assets = input<AssetListItem[]>([]);
  readonly saved = output<IncomeItem>();
}

@Component({
  selector: 'app-mark-paid-dialog',
  standalone: true,
  template: '',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
class MarkPaidDialogStubComponent {
  readonly visible = model(false);
  readonly income = input<IncomeItem | null>(null);
  readonly paid = output<IncomeItem>();
  readonly stale = output<void>();
}

const ASSETS: AssetListItem[] = [
  {
    id: 1,
    secid: 'SBER',
    isin: 'RU0009029540',
    name: 'Сбербанк',
    short_name: 'Сбербанк',
    type: 'STOCK',
    board: 'TQBR',
    currency: 'RUB',
    lot_size: 10,
    is_active: true,
  },
  {
    id: 2,
    secid: 'SU26238RMFS4',
    isin: 'RU000A0JX0J2',
    name: 'ОФЗ 26238',
    short_name: 'ОФЗ 26238',
    type: 'BOND',
    board: 'TQCB',
    currency: 'RUB',
    lot_size: 1,
    is_active: true,
  },
];

const PAID_DIVIDEND: IncomeItem = {
  id: 1,
  asset_id: 1,
  asset_secid: 'SBER',
  kind: 'DIVIDEND',
  status: 'PAID',
  amount_per_unit: '10.00',
  quantity: 20,
  amount_total: '200.00',
  currency: 'RUB',
  record_date: '2026-08-21',
  pay_date: '2026-09-15',
  source: 'MANUAL',
  note: 'Демо-дивиденд',
  is_overdue: false,
};

const PAID_COUPON: IncomeItem = {
  id: 2,
  asset_id: 2,
  asset_secid: 'SU26238RMFS4',
  kind: 'COUPON',
  status: 'PAID',
  amount_per_unit: '35.00',
  quantity: 15,
  amount_total: '525.00',
  currency: 'RUB',
  record_date: null,
  pay_date: '2026-09-20',
  source: 'MANUAL',
  note: 'Демо-купон',
  is_overdue: false,
};

const EXPECTED_COUPON: IncomeItem = {
  id: 3,
  asset_id: 2,
  asset_secid: 'SU26238RMFS4',
  kind: 'COUPON',
  status: 'EXPECTED',
  amount_per_unit: '35.00',
  quantity: 15,
  amount_total: '111.00',
  currency: 'RUB',
  record_date: null,
  pay_date: '2026-11-09',
  source: 'MOEX',
  note: null,
  is_overdue: true,
};

const TOTALS = {
  dividends_paid: '200.00',
  coupons_paid: '525.00',
  expected_coupons: '1575.00',
};

function response(items: IncomeItem[]): IncomeListResponse {
  return { items, totals: TOTALS };
}

const PAID_RESPONSE = response([PAID_DIVIDEND, PAID_COUPON]);
const EXPECTED_RESPONSE = response([EXPECTED_COUPON]);
const EMPTY_RESPONSE = response([]);

function normalize(value: string): string {
  return value.replace(/[\u00a0\u202f]/g, ' ');
}

describe('IncomePage', () => {
  let incomes: jasmine.SpyObj<IncomeService>;
  let assets: jasmine.SpyObj<AssetsService>;
  let notifications: jasmine.SpyObj<NotificationService>;
  let confirmation: jasmine.SpyObj<ConfirmationService>;

  beforeEach(async () => {
    incomes = jasmine.createSpyObj<IncomeService>('IncomeService', [
      'list',
      'create',
      'update',
      'markPaid',
      'remove',
    ]);
    incomes.list.and.callFake((filters) =>
      of(filters?.status === 'EXPECTED' ? EXPECTED_RESPONSE : PAID_RESPONSE),
    );

    assets = jasmine.createSpyObj<AssetsService>('AssetsService', ['list']);
    assets.list.and.returnValue(of({ items: ASSETS }));

    notifications = jasmine.createSpyObj<NotificationService>('NotificationService', [
      'success',
      'info',
      'warn',
      'error',
    ]);

    confirmation = jasmine.createSpyObj<ConfirmationService>('ConfirmationService', [
      'confirm',
    ]);
    confirmation.confirm.and.callFake((options) => options.accept?.());

    await TestBed.configureTestingModule({
      imports: [IncomePage],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
        { provide: IncomeService, useValue: incomes },
        { provide: AssetsService, useValue: assets },
        { provide: NotificationService, useValue: notifications },
        { provide: ConfirmationService, useValue: confirmation },
      ],
    })
      .overrideComponent(IncomePage, {
        remove: { imports: [IncomeFormDialogComponent, MarkPaidDialogComponent] },
        add: { imports: [IncomeFormDialogStubComponent, MarkPaidDialogStubComponent] },
      })
      .compileComponents();
  });

  function create(): ComponentFixture<IncomePage> {
    const fixture = TestBed.createComponent(IncomePage);
    fixture.detectChanges();
    return fixture;
  }

  it('loads PAID by default and renders portfolio totals and rows', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;
    const content = normalize(element.textContent ?? '');

    expect(incomes.list).toHaveBeenCalledWith({
      status: 'PAID',
      kind: undefined,
      assetId: undefined,
      from: undefined,
      to: undefined,
    });
    expect(element.querySelectorAll('app-stat-card').length).toBe(3);
    expect(content).toContain('По всему портфелю');
    expect(content).toContain('1 575,00 ₽');
    expect(content).toContain('200,00 ₽');
    expect(content).toContain('525,00 ₽');
    expect(content).toContain('SBER');
    expect(content).toContain('SU26238RMFS4');
    expect(element.querySelectorAll('p-table tbody tr').length).toBe(2);
    expect(element.querySelector('p-table table')?.getAttribute('aria-labelledby')).toBe(
      'income-list-title',
    );
    expect(element.querySelectorAll('p-tab').length).toBe(2);
    expect(element.querySelector('p-tab[value="PAID"]')?.getAttribute('role')).toBe('tab');
  });

  it('switches tabs and keeps the active filters in the next request', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.onKindChange('COUPON');
    component.onStatusChange('EXPECTED');
    fixture.detectChanges();

    expect(incomes.list.calls.mostRecent().args[0]).toEqual({
      status: 'EXPECTED',
      kind: 'COUPON',
      assetId: undefined,
      from: undefined,
      to: undefined,
    });
    expect(component.status()).toBe('EXPECTED');
    expect(normalize(fixture.nativeElement.textContent)).toContain('Ожидаемые купоны');
  });

  it('sends kind, asset and ISO date filters and resets them', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.onKindChange('COUPON');
    component.onAssetChange(2);
    component.onFromChange(new Date(2026, 0, 1));
    component.onToChange(new Date(2026, 11, 31));

    expect(incomes.list.calls.mostRecent().args[0]).toEqual({
      status: 'PAID',
      kind: 'COUPON',
      assetId: 2,
      from: '2026-01-01',
      to: '2026-12-31',
    });
    expect(component.hasFilters()).toBeTrue();

    component.resetFilters();
    fixture.detectChanges();

    expect(incomes.list.calls.mostRecent().args[0]).toEqual({
      status: 'PAID',
      kind: undefined,
      assetId: undefined,
      from: undefined,
      to: undefined,
    });
    expect(component.hasFilters()).toBeFalse();
  });

  it('keeps server totals unchanged while filters are active', () => {
    incomes.list.and.returnValues(of(PAID_RESPONSE), of(response([PAID_DIVIDEND])));

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    fixture.componentInstance.onKindChange('DIVIDEND');
    fixture.detectChanges();

    const content = normalize(element.textContent ?? '');
    expect(element.querySelectorAll('p-table tbody tr').length).toBe(1);
    expect(element.querySelectorAll('app-stat-card').length).toBe(3);
    expect(content).toContain('200,00 ₽');
    expect(content).toContain('525,00 ₽');
    expect(content).toContain('1 575,00 ₽');
    expect(content).toContain('По всему портфелю');
  });

  it('shows an error state instead of stale rows when a filter request fails', () => {
    incomes.list.and.returnValues(
      of(PAID_RESPONSE),
      throwError(() => new ApiError(0, 'NETWORK_ERROR', 'Нет связи с backend')),
      of(PAID_RESPONSE),
    );

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;
    const component = fixture.componentInstance;
    const assetCalls = assets.list.calls.count();

    component.onKindChange('COUPON');
    fixture.detectChanges();

    expect(element.querySelector('app-error-state')).toBeTruthy();
    expect(element.querySelector('p-table')).toBeNull();
    expect(normalize(element.textContent ?? '')).toContain('Нет связи с backend');

    component.retry();
    fixture.detectChanges();

    expect(assets.list.calls.count()).toBe(assetCalls + 1);
    expect(incomes.list.calls.count()).toBe(3);
    expect(element.querySelector('app-error-state')).toBeNull();
    expect(element.querySelectorAll('p-table tbody tr').length).toBe(2);
  });

  it('warns once when the asset filter cannot load across retries', () => {
    assets.list.and.returnValue(
      throwError(() => new ApiError(0, 'NETWORK_ERROR', 'Нет связи с backend')),
    );

    const fixture = create();
    const component = fixture.componentInstance;

    component.retry();
    component.retry();

    expect(assets.list).toHaveBeenCalledTimes(3);
    expect(notifications.warn).toHaveBeenCalledTimes(1);
  });

  it('does not let a late response overwrite the newer tab', () => {
    const paid = new Subject<IncomeListResponse>();
    const expected = new Subject<IncomeListResponse>();
    incomes.list.and.returnValues(paid.asObservable(), expected.asObservable());

    const fixture = create();
    const component = fixture.componentInstance;

    expect(fixture.nativeElement.querySelector('app-loading-skeleton')).toBeTruthy();

    component.onStatusChange('EXPECTED');

    expected.next(EXPECTED_RESPONSE);
    expected.complete();
    fixture.detectChanges();
    expect(component.items().map((item) => item.id)).toEqual([3]);

    paid.next(PAID_RESPONSE);
    paid.complete();
    fixture.detectChanges();

    expect(component.status()).toBe('EXPECTED');
    expect(component.items().map((item) => item.id)).toEqual([3]);
  });

  it('shows an overdue badge on expected coupons', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.onStatusChange('EXPECTED');
    fixture.detectChanges();

    const content = normalize(fixture.nativeElement.textContent ?? '');
    expect(content).toContain('Просрочен');
    expect(content).toContain('Ожидается');
  });

  it('shows tab-aware empty states and filter reset action', () => {
    incomes.list.and.returnValue(of(EMPTY_RESPONSE));

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;
    const component = fixture.componentInstance;

    expect(normalize(element.textContent ?? '')).toContain('Выплаченных доходов пока нет');

    component.onKindChange('DIVIDEND');
    fixture.detectChanges();
    expect(normalize(element.textContent ?? '')).toContain('По выбранным фильтрам доходов нет');
    expect(element.querySelector('.income__filter-actions button')).toBeTruthy();

    component.resetFilters();
    component.onStatusChange('EXPECTED');
    fixture.detectChanges();
    expect(normalize(element.textContent ?? '')).toContain('Ожидаемых купонов нет');
  });

  it('shows an error state and retries', () => {
    incomes.list.and.returnValues(
      throwError(() => new ApiError(0, 'NETWORK_ERROR', 'Нет связи с backend')),
      of(PAID_RESPONSE),
    );

    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    expect(normalize(element.textContent ?? '')).toContain('Нет связи с backend');

    element.querySelector<HTMLButtonElement>('app-error-state button')?.click();
    fixture.detectChanges();

    expect(incomes.list).toHaveBeenCalledTimes(2);
    expect(element.querySelector('app-error-state')).toBeNull();
    expect(element.querySelectorAll('p-table tbody tr').length).toBe(2);
  });

  it('shows a skeleton until the first response arrives', () => {
    const pending = new Subject<IncomeListResponse>();
    incomes.list.and.returnValue(pending.asObservable());

    const fixture = TestBed.createComponent(IncomePage);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('app-loading-skeleton')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('p-table')).toBeNull();

    pending.next(PAID_RESPONSE);
    pending.complete();
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('app-loading-skeleton')).toBeNull();
    expect(fixture.nativeElement.querySelectorAll('p-table tbody tr').length).toBe(2);
  });

  it('opens create, edit and mark-paid dialogs', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.openCreate();
    expect(component.formVisible()).toBeTrue();
    expect(component.editingIncome()).toBeNull();

    component.openEdit(PAID_DIVIDEND);
    expect(component.editingIncome()?.id).toBe(1);

    component.openMarkPaid(EXPECTED_COUPON);
    expect(component.markPaidVisible()).toBeTrue();
    expect(component.markingPaidIncome()?.id).toBe(3);
  });

  it('switches to PAID after saving a manual income created from EXPECTED', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.onStatusChange('EXPECTED');
    const callsBeforeSave = incomes.list.calls.count();

    component.onIncomeSaved(PAID_DIVIDEND);
    fixture.detectChanges();

    expect(component.status()).toBe('PAID');
    expect(incomes.list.calls.count()).toBe(callsBeforeSave + 1);
    expect(incomes.list.calls.mostRecent().args[0]?.status).toBe('PAID');
  });

  it('reloads after editing an income in the same tab', () => {
    const fixture = create();
    const component = fixture.componentInstance;
    const callsBefore = incomes.list.calls.count();

    component.onIncomeSaved({ ...PAID_DIVIDEND, amount_total: '250.00' });
    fixture.detectChanges();

    expect(component.status()).toBe('PAID');
    expect(incomes.list.calls.count()).toBe(callsBefore + 1);
    expect(incomes.list.calls.mostRecent().args[0]?.status).toBe('PAID');
  });

  it('reloads the list after mark-paid and after a stale 409', () => {
    const fixture = create();
    const component = fixture.componentInstance;
    const callsBefore = incomes.list.calls.count();

    component.onIncomePaid();
    expect(incomes.list.calls.count()).toBe(callsBefore + 1);

    component.onIncomeStale();
    expect(incomes.list.calls.count()).toBe(callsBefore + 2);
  });

  it('confirms deletion and reloads after 204', () => {
    incomes.remove.and.returnValue(of(void 0));
    const fixture = create();
    const component = fixture.componentInstance;
    const callsBefore = incomes.list.calls.count();

    component.deleteIncome(PAID_DIVIDEND);
    fixture.detectChanges();

    expect(confirmation.confirm).toHaveBeenCalled();
    expect(incomes.remove).toHaveBeenCalledWith(1);
    expect(notifications.success).toHaveBeenCalledWith('Доход удалён');
    expect(incomes.list.calls.count()).toBe(callsBefore + 1);
  });

  it('ignores a repeated delete while the first request is in flight', () => {
    const pending = new Subject<void>();
    incomes.remove.and.returnValue(pending.asObservable());

    const fixture = create();
    const component = fixture.componentInstance;

    component.deleteIncome(PAID_DIVIDEND);
    component.deleteIncome(PAID_DIVIDEND);

    expect(confirmation.confirm).toHaveBeenCalledTimes(2);
    expect(incomes.remove).toHaveBeenCalledTimes(1);
    expect(component.deletingIncomeId()).toBe(1);

    pending.next();
    pending.complete();
    fixture.detectChanges();

    expect(component.deletingIncomeId()).toBeNull();
  });

  it('warns that MOEX can recreate a deleted expected coupon', () => {
    incomes.remove.and.returnValue(of(void 0));
    const fixture = create();

    fixture.componentInstance.deleteIncome(EXPECTED_COUPON);

    const options = confirmation.confirm.calls.mostRecent().args[0];
    expect(String(options.message)).toContain('MOEX может создать его снова');
  });

  it('keeps the list intact when deletion fails', () => {
    incomes.remove.and.returnValue(
      throwError(() => new ApiError(409, 'BAD_REQUEST', 'Нельзя удалить доход', {})),
    );
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;
    const callsBefore = incomes.list.calls.count();

    fixture.componentInstance.deleteIncome(PAID_DIVIDEND);
    fixture.detectChanges();

    expect(notifications.error).toHaveBeenCalled();
    expect(incomes.list.calls.count()).toBe(callsBefore);
    expect(element.querySelectorAll('p-table tbody tr').length).toBe(2);
  });
});
