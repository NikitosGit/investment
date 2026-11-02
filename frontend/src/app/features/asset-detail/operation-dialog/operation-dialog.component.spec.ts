import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import Aura from '@primeuix/themes/aura';
import { providePrimeNG } from 'primeng/config';
import { of, throwError } from 'rxjs';

import { ApiError } from '../../../core/api/api-error';
import type { AssetDetail, OperationResponse } from '../../../core/api/models';
import { NotificationService } from '../../../core/services/notification.service';
import { OperationsService } from '../../../core/services/operations.service';
import { OperationDialogComponent } from './operation-dialog.component';

const STOCK: AssetDetail = {
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

const BOND: AssetDetail = {
  id: 2,
  secid: 'SU26238RMFS4',
  isin: 'RU000A0JX0J2',
  name: 'ОФЗ 26238',
  short_name: 'ОФЗ 26238',
  type: 'BOND',
  board: 'TQCB',
  currency: 'RUB',
  initial_face_value: '1000.00',
  current_face_value: '800.00',
  lot_size: 1,
  is_active: true,
  amortizations: [
    {
      id: 1,
      amortization_date: '2026-09-30',
      amount_per_unit: '200.00',
      source: 'MANUAL',
    },
  ],
};

const OPERATION: OperationResponse = {
  id: 5,
  asset_id: 1,
  type: 'BUY',
  trade_date: '2026-10-29',
  quantity: 5,
  input_price: '300.000000',
  input_price_type: 'RUB',
  price_rub: '300.000000',
  note: 'Тестовая покупка',
};

function normalize(value: string): string {
  return value.replace(/[\u00a0\u202f]/g, ' ');
}

describe('OperationDialogComponent', () => {
  let operations: jasmine.SpyObj<OperationsService>;
  let notifications: jasmine.SpyObj<NotificationService>;

  beforeEach(async () => {
    operations = jasmine.createSpyObj<OperationsService>('OperationsService', [
      'list',
      'create',
      'update',
      'remove',
    ]);
    operations.create.and.returnValue(
      of({ ...OPERATION, id: 6, trade_date: '2026-10-29', quantity: 5 }),
    );
    operations.update.and.returnValue(of({ ...OPERATION, quantity: 6 }));

    notifications = jasmine.createSpyObj<NotificationService>('NotificationService', [
      'success',
      'info',
      'warn',
      'error',
    ]);

    await TestBed.configureTestingModule({
      imports: [OperationDialogComponent],
      providers: [
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
        { provide: OperationsService, useValue: operations },
        { provide: NotificationService, useValue: notifications },
      ],
    }).compileComponents();
  });

  function create(
    asset: AssetDetail = STOCK,
    operation: OperationResponse | null = null,
  ): ComponentFixture<OperationDialogComponent> {
    const fixture = TestBed.createComponent(OperationDialogComponent);
    fixture.componentRef.setInput('asset', asset);
    fixture.componentRef.setInput('operation', operation);
    fixture.componentRef.setInput('visible', true);
    fixture.detectChanges();
    return fixture;
  }

  it('requires a quantity and a price before sending a request', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.form.controls.quantity.setValue('');
    component.form.controls.price.setValue('');
    component.submit();

    expect(operations.create).not.toHaveBeenCalled();
    expect(component.submitted()).toBeTrue();
    expect(component.showError('quantity')).toBeTrue();
    expect(component.showError('price')).toBeTrue();
  });

  it('moves focus to the first invalid field after submit', fakeAsync(() => {
    const fixture = create();
    const component = fixture.componentInstance;
    tick(10);

    component.form.patchValue({ trade_date: null, quantity: '', price: '' });
    component.submit();

    expect(document.activeElement?.id).toBe('operation-trade-date');
  }));

  it('exposes a modal dialog, traps focus and closes on Escape', fakeAsync(() => {
    const trigger = document.createElement('button');
    trigger.id = 'dialog-trigger';
    document.body.appendChild(trigger);

    const fixture = TestBed.createComponent(OperationDialogComponent);
    fixture.componentRef.setInput('asset', STOCK);
    fixture.componentRef.setInput('operation', null);
    trigger.focus();
    fixture.componentRef.setInput('visible', true);
    fixture.detectChanges();
    tick(10);

    const dialog = document.querySelector('[role="dialog"]') as HTMLElement | null;
    expect(dialog?.getAttribute('aria-modal')).toBe('true');

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    fixture.detectChanges();
    tick(10);

    expect(fixture.componentInstance.visible()).toBeFalse();
    expect(document.activeElement).toBe(trigger);

    trigger.remove();
  }));

  it('links the trade date error to the date field', () => {
    const fixture = create();
    const component = fixture.componentInstance;

    component.form.controls.trade_date.setValue(null);
    component.submit();
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector(
      '#operation-trade-date',
    ) as HTMLInputElement;
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.getAttribute('aria-describedby')).toBe('operation-trade-date-error');
  });

  it('creates a stock operation with the price kept as a decimal string', () => {
    const fixture = create();
    const component = fixture.componentInstance;
    const saved: number[] = [];
    component.saved.subscribe(() => saved.push(1));

    component.form.patchValue({
      type: 'BUY',
      trade_date: new Date(2026, 9, 29),
      quantity: '5',
      price: '300,00',
      note: ' Покупка ',
    });
    component.submit();

    expect(operations.create).toHaveBeenCalledWith({
      asset_id: 1,
      type: 'BUY',
      trade_date: '2026-10-29',
      quantity: 5,
      price: '300',
      price_type: 'RUB',
      note: 'Покупка',
    });
    expect(saved.length).toBe(1);
    expect(component.visible()).toBeFalse();
    expect(notifications.success).toHaveBeenCalled();
  });

  it('defaults a bond to PERCENT, shows the face value and sends PERCENT', () => {
    const fixture = create(BOND);
    const component = fixture.componentInstance;

    expect(component.form.controls.price_type.value).toBe('PERCENT');
    expect(normalize(fixture.nativeElement.textContent)).toContain('Текущий номинал: 800,00 ₽');

    component.form.patchValue({
      trade_date: new Date(2026, 9, 29),
      quantity: '1',
      price: '97.6',
    });
    component.submit();

    expect(operations.create).toHaveBeenCalledWith({
      asset_id: 2,
      type: 'BUY',
      trade_date: '2026-10-29',
      quantity: 1,
      price: '97.6',
      price_type: 'PERCENT',
      note: null,
    });
  });

  it('patches only the changed fields when editing', () => {
    const fixture = create(STOCK, OPERATION);
    const component = fixture.componentInstance;

    component.form.controls.quantity.setValue('6');
    component.submit();

    expect(operations.update).toHaveBeenCalledWith(5, { quantity: 6 });
    expect(operations.create).not.toHaveBeenCalled();
  });

  it('keeps entered values when the asset input changes while the dialog is open', () => {
    const fixture = create(STOCK);
    const component = fixture.componentInstance;

    component.form.patchValue({
      quantity: '5',
      price: '300,5',
      note: 'Не сбрасывать',
    });

    fixture.componentRef.setInput('asset', BOND);
    fixture.detectChanges();

    expect(component.form.controls.quantity.value).toBe('5');
    expect(component.form.controls.price.value).toBe('300,5');
    expect(component.form.controls.note.value).toBe('Не сбрасывать');
  });

  it('sends note: null when a non-empty note is cleared', () => {
    const fixture = create(STOCK, OPERATION);
    const component = fixture.componentInstance;

    component.form.controls.note.setValue('');
    component.submit();

    expect(operations.update).toHaveBeenCalledWith(5, { note: null });
  });

  it('closes without a request when nothing changed', () => {
    const fixture = create(STOCK, OPERATION);
    const component = fixture.componentInstance;

    component.submit();

    expect(operations.update).not.toHaveBeenCalled();
    expect(component.visible()).toBeFalse();
    expect(notifications.info).toHaveBeenCalledWith('Изменений нет');
  });

  it('keeps the dialog open and explains an oversell 409', () => {
    operations.create.and.returnValue(
      throwError(
        () =>
          new ApiError(409, 'INSUFFICIENT_QUANTITY', 'Нельзя продать 20: доступно 15', {
            available: 15,
            requested: 20,
          }),
      ),
    );

    const fixture = create();
    const component = fixture.componentInstance;

    component.form.patchValue({
      type: 'SELL',
      trade_date: new Date(2026, 9, 29),
      quantity: '20',
      price: '300',
    });
    component.submit();

    expect(component.visible()).toBeTrue();
    expect(component.serverError()).toContain('Нельзя продать 20: доступно 15');
    expect(component.form.controls.quantity.errors?.['insufficient']).toBeTrue();
  });

  it('maps 422 field errors onto controls', () => {
    operations.create.and.returnValue(
      throwError(
        () =>
          new ApiError(422, 'VALIDATION_ERROR', 'Ошибка валидации данных', {
            errors: [{ field: 'body.price', message: 'must be greater than 0', type: 'greater_than' }],
          }),
      ),
    );

    const fixture = create();
    const component = fixture.componentInstance;

    component.form.patchValue({
      trade_date: new Date(2026, 9, 29),
      quantity: '1',
      price: '300',
    });
    component.submit();

    expect(component.visible()).toBeTrue();
    expect(component.serverError()).toBe('Ошибка валидации данных');
    expect(component.form.controls.price.errors?.['server']).toBe('Проверьте значение поля.');
  });
});
