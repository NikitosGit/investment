import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import Aura from '@primeuix/themes/aura';
import { providePrimeNG } from 'primeng/config';
import { of, throwError } from 'rxjs';

import { ApiError } from '../../../core/api/api-error';
import type { IncomeItem } from '../../../core/api/models';
import { IncomeService } from '../../../core/services/income.service';
import { NotificationService } from '../../../core/services/notification.service';
import { MarkPaidDialogComponent } from './mark-paid-dialog.component';

const EXPECTED: IncomeItem = {
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
};

const PAID: IncomeItem = { ...EXPECTED, status: 'PAID' };

describe('MarkPaidDialogComponent', () => {
  let incomes: jasmine.SpyObj<IncomeService>;
  let notifications: jasmine.SpyObj<NotificationService>;

  beforeEach(async () => {
    incomes = jasmine.createSpyObj<IncomeService>('IncomeService', ['markPaid']);
    incomes.markPaid.and.returnValue(of(PAID));

    notifications = jasmine.createSpyObj<NotificationService>('NotificationService', [
      'success',
      'info',
      'warn',
      'error',
    ]);

    await TestBed.configureTestingModule({
      imports: [MarkPaidDialogComponent],
      providers: [
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
        { provide: IncomeService, useValue: incomes },
        { provide: NotificationService, useValue: notifications },
      ],
    }).compileComponents();
  });

  function create(income: IncomeItem = EXPECTED): ComponentFixture<MarkPaidDialogComponent> {
    const fixture = TestBed.createComponent(MarkPaidDialogComponent);
    fixture.componentRef.setInput('income', income);
    fixture.componentRef.setInput('visible', true);
    fixture.detectChanges();
    return fixture;
  }

  it('prefills the expected amount and pay date', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    expect(component.form.controls.amount_total.value).toBe('525.00');
    expect(component.form.controls.pay_date.value).toEqual(new Date(2026, 10, 9));
  });

  it('confirms the payment, emits the PAID row and reloads', () => {
    const fixture = create();
    const component = fixture.componentInstance;
    const paid: IncomeItem[] = [];
    component.paid.subscribe((income) => paid.push(income));

    component.submit();

    expect(incomes.markPaid).toHaveBeenCalledWith(3, {
      amount_total: '525',
      pay_date: '2026-11-09',
    });
    expect(paid.length).toBe(1);
    expect(component.visible()).toBeFalse();
    expect(notifications.success).toHaveBeenCalledWith('Выплата подтверждена');
  });

  it('sends an empty body when the amount and date are cleared', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.form.controls.amount_total.setValue('');
    component.form.controls.pay_date.setValue(null);
    component.submit();

    expect(incomes.markPaid).toHaveBeenCalledWith(3, {});
  });

  it('sends only the pay date when the amount is cleared', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.form.controls.amount_total.setValue('');
    component.submit();

    expect(incomes.markPaid).toHaveBeenCalledWith(3, { pay_date: '2026-11-09' });
  });

  it('rejects a non-positive amount before sending', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.form.controls.amount_total.setValue('0');
    component.submit();

    expect(incomes.markPaid).not.toHaveBeenCalled();
    expect(component.showError('amount_total')).toBeTrue();
    expect(component.errorText('amount_total')).toContain('больше нуля');
  });

  it('focuses the invalid amount and links hints to the date field', fakeAsync(() => {
    const fixture = create();
    const component = fixture.componentInstance;
    const element = fixture.nativeElement as HTMLElement;
    tick(10);

    component.form.controls.amount_total.setValue('0');
    component.submit();
    fixture.detectChanges();

    expect(document.activeElement?.id).toBe('mark-paid-amount');
    expect(
      element.querySelector('#mark-paid-date')?.getAttribute('aria-describedby'),
    ).toBe('mark-paid-date-hint');
  }));

  it('keeps entered values when the income input changes while the dialog is open', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.form.patchValue({
      amount_total: '500',
      pay_date: new Date(2026, 11, 1),
    });

    fixture.componentRef.setInput('income', { ...EXPECTED, id: 4, amount_total: '999.00' });
    fixture.detectChanges();

    expect(component.form.controls.amount_total.value).toBe('500');
    expect(component.form.controls.pay_date.value).toEqual(new Date(2026, 11, 1));
  });

  it('maps 422 field errors onto the amount control', () => {
    incomes.markPaid.and.returnValue(
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

    component.submit();

    expect(component.visible()).toBeTrue();
    expect(component.serverError()).toBe('Ошибка валидации данных');
    expect(component.form.controls.amount_total.errors?.['server']).toBe(
      'Input should be greater than 0',
    );
  });

  it('keeps the dialog open for a generic 409 conflict', () => {
    incomes.markPaid.and.returnValue(
      throwError(
        () =>
          new ApiError(409, 'CONFLICT', 'Доход изменён другим запросом', {
            income_id: 3,
          }),
      ),
    );

    const fixture = create();
    const component = fixture.componentInstance;
    let stale = 0;
    component.stale.subscribe(() => (stale += 1));

    component.submit();

    expect(component.visible()).toBeTrue();
    expect(component.serverError()).toBe('Доход изменён другим запросом');
    expect(stale).toBe(0);
    expect(notifications.warn).not.toHaveBeenCalled();
  });

  it('closes and reloads on 409 INCOME_ALREADY_PAID', () => {
    incomes.markPaid.and.returnValue(
      throwError(
        () =>
          new ApiError(409, 'INCOME_ALREADY_PAID', 'Доход 3 уже выплачен', {
            income_id: 3,
          }),
      ),
    );

    const fixture = create();
    const component = fixture.componentInstance;
    let stale = 0;
    let paid = 0;
    component.stale.subscribe(() => (stale += 1));
    component.paid.subscribe(() => (paid += 1));

    component.submit();

    expect(component.visible()).toBeFalse();
    expect(stale).toBe(1);
    expect(paid).toBe(0);
    expect(notifications.warn).toHaveBeenCalled();
    expect(notifications.success).not.toHaveBeenCalled();
  });
});
