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
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DatePickerModule } from 'primeng/datepicker';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { finalize } from 'rxjs';

import { mapHttpError } from '../../../core/api/api-error';
import type { IncomeItem, MarkPaidIn } from '../../../core/api/models';
import { isoToDate, toIsoDate } from '../../../core/formatting/date-input';
import { incomeKindLabel } from '../../../core/formatting/labels';
import { MoneyPipe } from '../../../core/formatting/money.pipe';
import {
  optionalPositiveDecimalValidator,
  trimDecimalZeros,
} from '../../../core/formatting/validators';
import { IncomeService } from '../../../core/services/income.service';
import { NotificationService } from '../../../core/services/notification.service';
import { applyServerFieldErrors } from '../../../shared/forms/server-field-errors';

/** Confirmation dialog for an expected coupon (`POST /income/{id}/mark-paid`). */
@Component({
  selector: 'app-mark-paid-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    ButtonModule,
    DatePickerModule,
    DialogModule,
    InputTextModule,
    MessageModule,
    MoneyPipe,
  ],
  templateUrl: './mark-paid-dialog.component.html',
  styleUrl: './mark-paid-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MarkPaidDialogComponent {
  private readonly incomes = inject(IncomeService);
  private readonly notifications = inject(NotificationService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);

  readonly visible = model(false);
  readonly income = input<IncomeItem | null>(null);
  readonly paid = output<IncomeItem>();
  readonly stale = output<void>();

  readonly form = this.fb.group({
    amount_total: this.fb.nonNullable.control('', optionalPositiveDecimalValidator(2)),
    pay_date: this.fb.nonNullable.control<Date | null>(null),
  });

  readonly saving = signal(false);
  readonly serverError = signal<string | null>(null);

  readonly isExpected = computed(() => this.income()?.status === 'EXPECTED');
  readonly kindLabel = computed(() => {
    const income = this.income();
    return income ? incomeKindLabel(income.kind) : '';
  });

  constructor() {
    effect(() => {
      if (this.visible()) {
        this.resetForm();
      }
    });

    this.form.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.serverError.set(null));
  }

  showError(field: 'amount_total'): boolean {
    const control = this.form.controls[field];
    return control.invalid && control.touched;
  }

  errorText(field: 'amount_total'): string {
    const errors = this.form.controls[field].errors ?? {};

    if (errors['server']) {
      return String(errors['server']);
    }
    if (errors['positiveDecimal']) {
      return 'Сумма должна быть больше нуля, до 2 знаков после запятой.';
    }

    return 'Проверьте значение.';
  }

  submit(): void {
    this.form.markAllAsTouched();

    if (this.form.invalid || this.saving()) {
      return;
    }

    const income = this.income();
    if (!income) {
      return;
    }

    const raw = this.form.getRawValue();
    const payload: MarkPaidIn = {};
    const amount = raw.amount_total.trim();
    const payDate = toIsoDate(raw.pay_date);

    if (amount.length > 0) {
      payload.amount_total = trimDecimalZeros(amount);
    }
    if (payDate) {
      payload.pay_date = payDate;
    }

    this.saving.set(true);
    this.serverError.set(null);

    this.incomes
      .markPaid(income.id, payload)
      .pipe(
        finalize(() => this.saving.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (paidIncome) => {
          this.visible.set(false);
          this.notifications.success('Выплата подтверждена');
          this.paid.emit(paidIncome);
        },
        error: (error: unknown) => this.handleError(error),
      });
  }

  private handleError(error: unknown): void {
    const apiError = mapHttpError(error);

    if (apiError.code === 'INCOME_ALREADY_PAID') {
      // The expected row is stale: close the dialog and let the page refetch
      // so the coupon is not shown as pending anymore.
      this.visible.set(false);
      this.notifications.warn(
        'Этот доход уже выплачен. Список обновлён.',
        'Выплата уже подтверждена',
      );
      this.stale.emit();
      return;
    }

    this.serverError.set(apiError.message);

    if (apiError.code === 'VALIDATION_ERROR') {
      applyServerFieldErrors(this.form, apiError);
    }
  }

  private resetForm(): void {
    const income = this.income();

    this.form.reset({
      amount_total: income?.amount_total ?? '',
      pay_date: isoToDate(income?.pay_date),
    });
    this.serverError.set(null);
  }
}
