import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import Aura from '@primeuix/themes/aura';
import { providePrimeNG } from 'primeng/config';
import { of, throwError } from 'rxjs';

import { ApiError } from '../../../core/api/api-error';
import type { AssetListItem, IncomeItem } from '../../../core/api/models';
import { IncomeService } from '../../../core/services/income.service';
import { NotificationService } from '../../../core/services/notification.service';
import { IncomeFormDialogComponent } from './income-form-dialog.component';

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

const PAID_INCOME: IncomeItem = {
  id: 6,
  asset_id: 1,
  asset_secid: 'SBER',
  kind: 'DIVIDEND',
  status: 'PAID',
  amount_per_unit: '10.00',
  quantity: 20,
  amount_total: '200.00',
  currency: 'RUB',
  record_date: null,
  pay_date: '2026-09-15',
  source: 'MANUAL',
  note: 'Демо-дивиденд',
  is_overdue: false,
};

const EXPECTED_INCOME: IncomeItem = {
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
  source: 'MOEX',
  note: null,
  is_overdue: false,
};

describe('IncomeFormDialogComponent', () => {
  let incomes: jasmine.SpyObj<IncomeService>;
  let notifications: jasmine.SpyObj<NotificationService>;

  beforeEach(async () => {
    incomes = jasmine.createSpyObj<IncomeService>('IncomeService', [
      'create',
      'update',
    ]);
    incomes.create.and.returnValue(of(PAID_INCOME));
    incomes.update.and.returnValue(of(PAID_INCOME));

    notifications = jasmine.createSpyObj<NotificationService>('NotificationService', [
      'success',
      'info',
      'warn',
      'error',
    ]);

    await TestBed.configureTestingModule({
      imports: [IncomeFormDialogComponent],
      providers: [
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
        { provide: IncomeService, useValue: incomes },
        { provide: NotificationService, useValue: notifications },
      ],
    }).compileComponents();
  });

  function create(income: IncomeItem | null = null): ComponentFixture<IncomeFormDialogComponent> {
    const fixture = TestBed.createComponent(IncomeFormDialogComponent);
    fixture.componentRef.setInput('income', income);
    fixture.componentRef.setInput('assets', ASSETS);
    fixture.componentRef.setInput('visible', true);
    fixture.detectChanges();
    return fixture;
  }

  it('requires an asset, amount and pay date for a new income', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.form.controls.pay_date.setValue(null);
    component.form.controls.amount_total.setValue('');
    component.submit();

    expect(incomes.create).not.toHaveBeenCalled();
    expect(component.showError('asset_id')).toBeTrue();
    expect(component.showError('amount_total')).toBeTrue();
    expect(component.showError('pay_date')).toBeTrue();
  });

  it('moves focus to the first invalid field after submit', fakeAsync(() => {
    const fixture = create();
    const component = fixture.componentInstance;
    tick(10);

    component.form.patchValue({ asset_id: null, amount_total: '', pay_date: null });
    component.submit();

    expect(document.activeElement?.id).toBe('income-form-asset');
  }));

  it('associates select labels and the pay-date error with their controls', () => {
    const fixture = create();
    const component = fixture.componentInstance;
    const element = fixture.nativeElement as HTMLElement;

    expect(
      element.querySelector('#income-form-asset')?.getAttribute('aria-labelledby'),
    ).toBe('income-form-asset-label');
    expect(
      element.querySelector('#income-form-kind')?.getAttribute('aria-labelledby'),
    ).toBe('income-form-kind-label');

    component.form.controls.pay_date.setValue(null);
    component.submit();
    fixture.detectChanges();

    const dateInput = element.querySelector('#income-form-pay-date') as HTMLInputElement;
    expect(dateInput.getAttribute('aria-invalid')).toBe('true');
    expect(dateInput.getAttribute('aria-describedby')).toBe('income-form-pay-date-error');
    expect(
      element.querySelector('#income-form-asset')?.getAttribute('aria-describedby'),
    ).toBe('income-form-asset-error');
    expect(
      element.querySelector('#income-form-asset')?.getAttribute('aria-invalid'),
    ).toBe('true');
  });

  it('keeps entered values when input signals change while the dialog is open', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.form.patchValue({
      kind: 'COUPON',
      asset_id: 2,
      amount_total: '777,77',
      quantity: '15',
      note: 'Не сбрасывать',
      pay_date: new Date(2026, 10, 20),
    });

    fixture.componentRef.setInput('assets', [ASSETS[1]]);
    fixture.componentRef.setInput('income', PAID_INCOME);
    fixture.detectChanges();

    expect(component.form.controls.kind.value).toBe('COUPON');
    expect(component.form.controls.asset_id.value).toBe(2);
    expect(component.form.controls.amount_total.value).toBe('777,77');
    expect(component.form.controls.quantity.value).toBe('15');
    expect(component.form.controls.note.value).toBe('Не сбрасывать');
  });

  it('keeps the selected asset after choosing it in p-select', () => {
    const fixture = create();
    const component = fixture.componentInstance;
    const element = fixture.nativeElement as HTMLElement;

    const assetSelect = element.querySelector('#income-form-asset') as HTMLElement;
    assetSelect.click();
    fixture.detectChanges();

    const option = Array.from(
      document.querySelectorAll<HTMLElement>('.p-select-option'),
    ).find((candidate) => candidate.textContent?.includes('SBER'));
    expect(option).toBeTruthy();

    option?.click();
    fixture.detectChanges();

    expect(component.form.controls.asset_id.value).toBe(1);
    expect(element.querySelector('#income-form-asset')?.textContent).toContain('SBER');

    fixture.componentRef.setInput('assets', [...ASSETS]);
    fixture.detectChanges();

    expect(component.form.controls.asset_id.value).toBe(1);
  });

  it('creates a manual PAID income with optional fields and a normalized total', () => {
    const fixture = create();
    const component = fixture.componentInstance;
    const saved: IncomeItem[] = [];
    component.saved.subscribe((income) => saved.push(income));

    component.form.patchValue({
      kind: 'COUPON',
      asset_id: 1,
      amount_total: '150,5',
      pay_date: new Date(2026, 9, 27),
      quantity: '15',
      amount_per_unit: '10,033333',
      record_date: new Date(2026, 9, 1),
      note: ' Ручной доход ',
    });
    component.submit();

    expect(incomes.create).toHaveBeenCalledWith({
      asset_id: 1,
      kind: 'COUPON',
      amount_total: '150.5',
      pay_date: '2026-10-27',
      quantity: 15,
      amount_per_unit: '10.033333',
      record_date: '2026-10-01',
      note: 'Ручной доход',
    });
    expect(saved.length).toBe(1);
    expect(component.visible()).toBeFalse();
    expect(notifications.success).toHaveBeenCalledWith('Доход добавлен');
  });

  it('omits optional quantity, per-unit value and record date when blank', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.form.patchValue({
      asset_id: 1,
      amount_total: '150',
      pay_date: new Date(2026, 9, 27),
    });
    component.submit();

    expect(incomes.create).toHaveBeenCalledWith({
      asset_id: 1,
      kind: 'DIVIDEND',
      amount_total: '150',
      pay_date: '2026-10-27',
      note: null,
    });
  });

  it('rejects an amount with more than two decimals and a too long note', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.form.patchValue({
      asset_id: 1,
      amount_total: '150.123',
      pay_date: new Date(2026, 9, 27),
      note: 'x'.repeat(501),
    });
    component.submit();

    expect(incomes.create).not.toHaveBeenCalled();
    expect(component.showError('amount_total')).toBeTrue();
    expect(component.errorText('amount_total')).toContain('до 2 знаков');
    expect(component.showError('note')).toBeTrue();
    expect(component.errorText('note')).toContain('500');
  });

  it('maps 422 field errors onto the form', () => {
    incomes.create.and.returnValue(
      throwError(
        () =>
          new ApiError(422, 'VALIDATION_ERROR', 'Ошибка валидации данных', {
            errors: [
              {
                field: 'body.amount_total',
                message: 'Input should be greater than 0',
                type: 'greater_than',
              },
            ],
          }),
      ),
    );

    const fixture = create();
    const component = fixture.componentInstance;

    component.form.patchValue({
      asset_id: 1,
      amount_total: '150',
      pay_date: new Date(2026, 9, 27),
    });
    component.submit();

    expect(component.visible()).toBeTrue();
    expect(component.serverError()).toBe('Ошибка валидации данных');
    expect(component.form.controls.amount_total.errors?.['server']).toBe(
      'Input should be greater than 0',
    );
  });

  it('patches only changed PAID fields and never sends a per-unit value', () => {
    const fixture = create(PAID_INCOME);
    const component = fixture.componentInstance;

    component.form.patchValue({
      amount_total: '165,00',
      quantity: '16',
      pay_date: new Date(2026, 8, 16),
      amount_per_unit: '99.99',
      record_date: new Date(2026, 8, 1),
      note: ' Уточнено ',
    });
    component.submit();

    expect(incomes.update).toHaveBeenCalledWith(6, {
      amount_total: '165',
      quantity: 16,
      pay_date: '2026-09-16',
      note: 'Уточнено',
    });
  });

  it('accepts zero quantity for a PAID row', () => {
    const fixture = create(PAID_INCOME);
    const component = fixture.componentInstance;

    component.form.controls.quantity.setValue('0');
    component.submit();

    expect(incomes.update).toHaveBeenCalledWith(6, { quantity: 0 });
  });

  it('closes without a request when a PAID row is unchanged', () => {
    const fixture = create(PAID_INCOME);
    const component = fixture.componentInstance;

    component.submit();

    expect(incomes.update).not.toHaveBeenCalled();
    expect(component.visible()).toBeFalse();
    expect(notifications.info).toHaveBeenCalledWith('Изменений нет');
  });

  it('patches only note and record date for an EXPECTED coupon', () => {
    incomes.update.and.returnValue(of(EXPECTED_INCOME));
    const fixture = create(EXPECTED_INCOME);
    const component = fixture.componentInstance;

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('#income-form-total')).toBeNull();
    expect(element.querySelector('#income-form-quantity')).toBeNull();
    expect(element.querySelector('#income-form-pay-date')).toBeNull();
    expect(element.querySelector('#income-form-record-date')).toBeTruthy();

    component.form.patchValue({
      amount_total: '999.00',
      quantity: '99',
      pay_date: new Date(2030, 0, 1),
      record_date: new Date(2026, 9, 1),
      note: 'Уточнение купона',
    });
    component.submit();

    expect(incomes.update).toHaveBeenCalledWith(3, {
      note: 'Уточнение купона',
      record_date: '2026-10-01',
    });
  });

  it('ignores unchanged note when only record date changes for EXPECTED', () => {
    incomes.update.and.returnValue(of(EXPECTED_INCOME));
    const fixture = create({ ...EXPECTED_INCOME, note: 'Старый комментарий' });
    const component = fixture.componentInstance;

    component.form.controls.record_date.setValue(new Date(2026, 9, 5));
    component.submit();

    expect(incomes.update).toHaveBeenCalledWith(3, { record_date: '2026-10-05' });
  });

  it('keeps the dialog open and shows a 400 backend message for a PAID edit', () => {
    incomes.update.and.returnValue(
      throwError(
        () =>
          new ApiError(400, 'BAD_REQUEST', 'Нельзя сохранить выплату с нулевым количеством', {}),
      ),
    );

    const fixture = create(PAID_INCOME);
    const component = fixture.componentInstance;

    component.form.controls.quantity.setValue('0');
    component.submit();

    expect(component.visible()).toBeTrue();
    expect(component.serverError()).toBe('Нельзя сохранить выплату с нулевым количеством');
    expect(notifications.success).not.toHaveBeenCalled();
  });

  it('keeps the dialog open and shows a 400 backend message', () => {
    incomes.update.and.returnValue(
      throwError(
        () =>
          new ApiError(400, 'BAD_REQUEST', 'Ожидаемый купон рассчитывается автоматически', {}),
      ),
    );

    const fixture = create(EXPECTED_INCOME);
    const component = fixture.componentInstance;

    component.form.controls.note.setValue('Правка');
    component.submit();

    expect(component.visible()).toBeTrue();
    expect(component.serverError()).toBe('Ожидаемый купон рассчитывается автоматически');
    expect(notifications.success).not.toHaveBeenCalled();
  });
});
