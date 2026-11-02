import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  input,
  model,
  output,
  signal,
  untracked,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DatePickerModule } from 'primeng/datepicker';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { SelectModule } from 'primeng/select';
import { TextareaModule } from 'primeng/textarea';
import { finalize, type Observable } from 'rxjs';

import { mapHttpError } from '../../../core/api/api-error';
import type {
  AssetListItem,
  IncomeCreateIn,
  IncomeItem,
  IncomeKind,
  IncomeUpdateIn,
} from '../../../core/api/models';
import { isoToDate, toIsoDate } from '../../../core/formatting/date-input';
import { DatePipe } from '../../../core/formatting/date.pipe';
import {
  incomeKindLabel,
  incomeStatusLabel,
} from '../../../core/formatting/labels';
import { MoneyPipe } from '../../../core/formatting/money.pipe';
import {
  nonNegativeIntegerValidator,
  optionalPositiveDecimalValidator,
  positiveDecimalValidator,
  trimDecimalZeros,
} from '../../../core/formatting/validators';
import { IncomeService } from '../../../core/services/income.service';
import { NotificationService } from '../../../core/services/notification.service';
import { AriaDescribedByDirective } from '../../../shared/a11y/aria-described-by.directive';
import {
  focusFirstInvalidField,
  rememberActiveElement,
  restoreFocus,
} from '../../../shared/a11y/focus';
import { applyServerFieldErrors } from '../../../shared/forms/server-field-errors';
import type { SelectOption } from '../../../shared/ui/select-option';
import { toIncomeAssetOptions } from '../income-options';

type IncomeField =
  | 'asset_id'
  | 'kind'
  | 'amount_total'
  | 'pay_date'
  | 'quantity'
  | 'amount_per_unit'
  | 'record_date'
  | 'note';

interface IncomeSnapshot {
  amount_total: string;
  quantity: string;
  pay_date: string | null;
  note: string | null;
  record_date: string | null;
}

const REQUIRED_MESSAGES: Partial<Record<IncomeField, string>> = {
  asset_id: 'Выберите актив.',
  pay_date: 'Укажите дату выплаты.',
  amount_total: 'Укажите сумму дохода.',
  quantity: 'Укажите количество.',
};

const FIELD_IDS: Readonly<Record<IncomeField, string>> = {
  kind: 'income-form-kind',
  asset_id: 'income-form-asset',
  amount_total: 'income-form-total',
  pay_date: 'income-form-pay-date',
  quantity: 'income-form-quantity',
  amount_per_unit: 'income-form-per-unit',
  record_date: 'income-form-record-date',
  note: 'income-form-note',
};

/** Create/edit dialog for a manual income or an expected coupon. */
@Component({
  selector: 'app-income-form-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    ButtonModule,
    DatePickerModule,
    DialogModule,
    InputTextModule,
    MessageModule,
    SelectModule,
    TextareaModule,
    DatePipe,
    MoneyPipe,
    AriaDescribedByDirective,
  ],
  templateUrl: './income-form-dialog.component.html',
  styleUrl: './income-form-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class IncomeFormDialogComponent {
  private readonly incomes = inject(IncomeService);
  private readonly notifications = inject(NotificationService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);

  readonly visible = model(false);
  readonly income = input<IncomeItem | null>(null);
  readonly assets = input<AssetListItem[]>([]);
  readonly saved = output<IncomeItem>();

  readonly kindOptions: SelectOption<IncomeKind>[] = [
    { value: 'DIVIDEND', label: 'Дивиденд' },
    { value: 'COUPON', label: 'Купон' },
  ];

  readonly form = this.fb.group({
    kind: this.fb.nonNullable.control<IncomeKind>('DIVIDEND'),
    asset_id: this.fb.nonNullable.control<number | null>(null),
    amount_total: this.fb.nonNullable.control(''),
    pay_date: this.fb.nonNullable.control<Date | null>(null),
    quantity: this.fb.nonNullable.control(''),
    amount_per_unit: this.fb.nonNullable.control(''),
    record_date: this.fb.nonNullable.control<Date | null>(null),
    note: this.fb.nonNullable.control(''),
  });

  readonly saving = signal(false);
  readonly submitted = signal(false);
  readonly serverError = signal<string | null>(null);

  private original: IncomeSnapshot | null = null;
  private returnFocusTo: HTMLElement | null = null;
  private isOpen = false;

  readonly isEdit = computed(() => this.income() !== null);
  readonly isExpectedEdit = computed(() => this.income()?.status === 'EXPECTED');
  readonly isPaidEdit = computed(() => this.isEdit() && !this.isExpectedEdit());

  readonly title = computed(() => {
    if (!this.isEdit()) {
      return 'Новый доход';
    }

    return this.isExpectedEdit() ? 'Изменить ожидаемый купон' : 'Изменить выплату';
  });

  readonly assetOptions = computed<SelectOption<number>[]>(() =>
    toIncomeAssetOptions(this.assets()),
  );

  readonly assetLabel = computed(() => {
    const income = this.income();
    if (!income) {
      return '';
    }

    return (
      this.assetOptions().find((option) => option.value === income.asset_id)?.label ??
      income.asset_secid
    );
  });

  readonly kindLabel = computed(() => {
    const income = this.income();
    return income ? incomeKindLabel(income.kind) : '';
  });

  readonly statusLabel = computed(() => {
    const income = this.income();
    return income ? incomeStatusLabel(income.status) : '';
  });

  constructor() {
    this.configureValidators();

    effect(() => {
      const isVisible = this.visible();
      if (isVisible === this.isOpen) {
        return;
      }
      this.isOpen = isVisible;

      untracked(() => {
        if (isVisible) {
          this.returnFocusTo = rememberActiveElement();
          this.resetForm();
        } else {
          restoreFocus(this.returnFocusTo);
          this.returnFocusTo = null;
        }
      });
    });

    this.form.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.serverError.set(null));
  }

  showError(field: IncomeField): boolean {
    const control = this.form.controls[field];
    return control.invalid && (this.submitted() || control.touched);
  }

  errorText(field: IncomeField): string {
    const errors = this.form.controls[field].errors ?? {};

    if (errors['server']) {
      return String(errors['server']);
    }
    if (errors['required']) {
      return REQUIRED_MESSAGES[field] ?? 'Заполните поле.';
    }
    if (field === 'amount_total' && errors['positiveDecimal']) {
      return 'Сумма должна быть больше нуля, до 2 знаков после запятой.';
    }
    if (field === 'amount_per_unit' && errors['positiveDecimal']) {
      return 'Сумма за единицу должна быть больше нуля, до 6 знаков после запятой.';
    }
    if (field === 'quantity' && errors['nonNegativeInteger']) {
      return 'Количество должно быть целым неотрицательным числом.';
    }
    if (field === 'note' && errors['maxlength']) {
      return 'Не больше 500 символов.';
    }

    return 'Проверьте значение.';
  }

  submit(): void {
    this.submitted.set(true);
    this.form.markAllAsTouched();

    if (this.form.invalid) {
      focusFirstInvalidField(this.form, FIELD_IDS);
      return;
    }

    if (this.saving()) {
      return;
    }

    const income = this.income();
    if (income) {
      const payload = this.buildUpdatePayload(income);

      if (Object.keys(payload).length === 0) {
        this.notifications.info('Изменений нет');
        this.visible.set(false);
        return;
      }

      this.send(this.incomes.update(income.id, payload), 'Доход обновлён');
      return;
    }

    this.send(this.incomes.create(this.buildCreatePayload()), 'Доход добавлен');
  }

  private send(request$: Observable<IncomeItem>, successMessage: string): void {
    this.saving.set(true);
    this.serverError.set(null);

    request$
      .pipe(
        finalize(() => this.saving.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (income) => {
          this.visible.set(false);
          this.notifications.success(successMessage);
          this.saved.emit(income);
        },
        error: (error: unknown) => this.handleError(error),
      });
  }

  private handleError(error: unknown): void {
    const apiError = mapHttpError(error);
    this.serverError.set(apiError.message);

    if (apiError.code === 'VALIDATION_ERROR') {
      applyServerFieldErrors(this.form, apiError);
    }
  }

  private buildCreatePayload(): IncomeCreateIn {
    const raw = this.form.getRawValue();
    const payload: IncomeCreateIn = {
      asset_id: raw.asset_id as number,
      kind: raw.kind,
      amount_total: trimDecimalZeros(raw.amount_total),
      pay_date: toIsoDate(raw.pay_date) ?? '',
      note: this.trimmedNote(raw.note),
    };

    const quantity = raw.quantity.trim();
    if (quantity.length > 0) {
      payload.quantity = Number(quantity);
    }

    const amountPerUnit = raw.amount_per_unit.trim();
    if (amountPerUnit.length > 0) {
      payload.amount_per_unit = trimDecimalZeros(amountPerUnit);
    }

    const recordDate = toIsoDate(raw.record_date);
    if (recordDate) {
      payload.record_date = recordDate;
    }

    return payload;
  }

  private buildUpdatePayload(income: IncomeItem): IncomeUpdateIn {
    const current = this.buildSnapshot();
    const original = this.original;
    const payload: IncomeUpdateIn = {};

    if (!original) {
      return payload;
    }

    if (current.note !== original.note) {
      payload.note = current.note;
    }

    if (income.status === 'EXPECTED') {
      // Amount, quantity and pay date of an expected coupon are derived by the
      // backend and rejected by PATCH; only display fields are editable.
      if (current.record_date !== original.record_date) {
        payload.record_date = current.record_date;
      }
      return payload;
    }

    if (current.amount_total !== original.amount_total) {
      payload.amount_total = current.amount_total;
    }
    if (current.quantity !== original.quantity) {
      payload.quantity = Number(current.quantity.trim());
    }
    if (current.pay_date !== original.pay_date) {
      payload.pay_date = current.pay_date;
    }

    return payload;
  }

  private buildSnapshot(): IncomeSnapshot {
    const raw = this.form.getRawValue();

    return {
      amount_total: trimDecimalZeros(raw.amount_total),
      quantity: raw.quantity.trim(),
      pay_date: toIsoDate(raw.pay_date),
      note: this.trimmedNote(raw.note),
      record_date: toIsoDate(raw.record_date),
    };
  }

  private trimmedNote(note: string): string | null {
    const trimmed = note.trim();
    return trimmed.length > 0 ? trimmed : null;
  }

  private resetForm(): void {
    const income = this.income();
    const isExpected = income?.status === 'EXPECTED';
    const kind = income?.kind ?? 'DIVIDEND';

    this.form.reset({
      kind,
      asset_id: income?.asset_id ?? null,
      amount_total: income?.amount_total ? String(income.amount_total) : '',
      pay_date: income ? isoToDate(income.pay_date) : new Date(),
      quantity: income?.quantity !== null && income?.quantity !== undefined
        ? String(income.quantity)
        : '',
      amount_per_unit: '',
      record_date: income ? isoToDate(income.record_date) : null,
      note: income?.note ?? '',
    });

    this.original = income
      ? {
          amount_total: trimDecimalZeros(income.amount_total ?? ''),
          quantity:
            income.quantity !== null && income.quantity !== undefined
              ? String(income.quantity)
              : '',
          pay_date: income.pay_date,
          note: income.note,
          record_date: income.record_date,
        }
      : null;

    this.configureValidators(income);
    this.submitted.set(false);
    this.serverError.set(null);
  }

  private configureValidators(income: IncomeItem | null = this.income()): void {
    const isEdit = income !== null;
    const isExpected = income?.status === 'EXPECTED';
    const paidEdit = isEdit && !isExpected;

    this.form.controls.asset_id.setValidators(isEdit ? [] : [Validators.required]);

    this.form.controls.amount_total.setValidators(
      isExpected ? [] : [Validators.required, positiveDecimalValidator(2)],
    );

    this.form.controls.pay_date.setValidators(isExpected ? [] : [Validators.required]);

    this.form.controls.quantity.setValidators(
      isExpected
        ? []
        : paidEdit
          ? [Validators.required, nonNegativeIntegerValidator]
          : [nonNegativeIntegerValidator],
    );

    this.form.controls.amount_per_unit.setValidators(
      isEdit ? [] : [optionalPositiveDecimalValidator(6)],
    );

    this.form.controls.note.setValidators([Validators.maxLength(500)]);

    for (const control of Object.values(this.form.controls)) {
      control.updateValueAndValidity({ emitEvent: false });
    }
  }
}
