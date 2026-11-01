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
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DatePickerModule } from 'primeng/datepicker';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { SelectButtonModule } from 'primeng/selectbutton';
import { TextareaModule } from 'primeng/textarea';
import { finalize, type Observable } from 'rxjs';

import { mapHttpError, formFieldName, validationErrors } from '../../../core/api/api-error';
import type { ApiError } from '../../../core/api/api-error';
import type {
  AssetDetail,
  OperationCreateIn,
  OperationResponse,
  OperationType,
  OperationUpdateIn,
  PriceType,
} from '../../../core/api/models';
import { isoToDate, toIsoDate } from '../../../core/formatting/date-input';
import { MoneyPipe } from '../../../core/formatting/money.pipe';
import {
  positiveDecimalValidator,
  positiveIntegerValidator,
  trimDecimalZeros,
} from '../../../core/formatting/validators';
import { NotificationService } from '../../../core/services/notification.service';
import { OperationsService } from '../../../core/services/operations.service';
import type { SelectOption } from '../../../shared/ui/select-option';

interface OperationSnapshot {
  type: OperationType;
  trade_date: string;
  quantity: number;
  price: string;
  price_type: PriceType;
  note: string | null;
}

type OperationField = 'type' | 'trade_date' | 'quantity' | 'price' | 'price_type' | 'note';

const REQUIRED_MESSAGES: Partial<Record<OperationField, string>> = {
  trade_date: 'Укажите дату сделки.',
  quantity: 'Укажите количество.',
  price: 'Укажите цену.',
};

/** Create/edit dialog for a BUY or SELL operation. */
@Component({
  selector: 'app-operation-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    ButtonModule,
    DatePickerModule,
    DialogModule,
    InputTextModule,
    MessageModule,
    SelectButtonModule,
    TextareaModule,
    MoneyPipe,
  ],
  templateUrl: './operation-dialog.component.html',
  styleUrl: './operation-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OperationDialogComponent {
  private readonly operations = inject(OperationsService);
  private readonly notifications = inject(NotificationService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);

  readonly visible = model(false);
  readonly asset = input.required<AssetDetail>();
  readonly operation = input<OperationResponse | null>(null);
  readonly saved = output<void>();

  readonly typeOptions: SelectOption<OperationType>[] = [
    { value: 'BUY', label: 'Покупка' },
    { value: 'SELL', label: 'Продажа' },
  ];

  readonly priceTypeOptions: SelectOption<PriceType>[] = [
    { value: 'PERCENT', label: '% от номинала' },
    { value: 'RUB', label: 'Рубли' },
  ];

  readonly form = this.fb.group({
    type: this.fb.nonNullable.control<OperationType>('BUY'),
    trade_date: this.fb.nonNullable.control<Date | null>(null, Validators.required),
    quantity: this.fb.nonNullable.control('', [
      Validators.required,
      positiveIntegerValidator,
    ]),
    price: this.fb.nonNullable.control('', [
      Validators.required,
      positiveDecimalValidator(6),
    ]),
    price_type: this.fb.nonNullable.control<PriceType>('RUB'),
    note: this.fb.nonNullable.control('', Validators.maxLength(500)),
  });

  readonly priceType = toSignal(this.form.controls.price_type.valueChanges, {
    initialValue: this.form.controls.price_type.value,
  });

  readonly saving = signal(false);
  readonly submitted = signal(false);
  readonly serverError = signal<string | null>(null);

  private original: OperationSnapshot | null = null;

  readonly isBond = computed(() => this.asset().type === 'BOND');
  readonly isEdit = computed(() => this.operation() !== null);
  readonly title = computed(() => (this.isEdit() ? 'Изменить операцию' : 'Новая операция'));
  readonly faceValue = computed(() => this.asset().current_face_value);

  readonly priceLabel = computed(() =>
    this.isBond() && this.priceType() === 'PERCENT'
      ? 'Цена, % от номинала'
      : 'Цена, ₽ за единицу',
  );

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

  showError(field: OperationField): boolean {
    const control = this.form.controls[field];
    return control.invalid && (this.submitted() || control.touched);
  }

  errorText(field: OperationField): string {
    const errors = this.form.controls[field].errors ?? {};

    if (errors['server']) {
      return String(errors['server']);
    }
    if (field === 'quantity' && errors['insufficient']) {
      return 'Недостаточно бумаг: уменьшите количество.';
    }
    if (errors['required']) {
      return REQUIRED_MESSAGES[field] ?? 'Заполните поле.';
    }
    if (field === 'quantity' && errors['positiveInteger']) {
      return 'Количество должно быть целым числом больше нуля.';
    }
    if (field === 'price' && errors['positiveDecimal']) {
      return 'Цена должна быть больше нуля, до 6 знаков после запятой.';
    }
    if (field === 'note' && errors['maxlength']) {
      return 'Не больше 500 символов.';
    }

    return 'Проверьте значение.';
  }

  submit(): void {
    this.submitted.set(true);
    this.form.markAllAsTouched();

    if (this.form.invalid || this.saving()) {
      return;
    }

    const operation = this.operation();
    if (operation) {
      const payload = this.buildUpdatePayload();

      if (Object.keys(payload).length === 0) {
        this.notifications.info('Изменений нет');
        this.visible.set(false);
        return;
      }

      this.send(this.operations.update(operation.id, payload), 'Операция обновлена');
      return;
    }

    this.send(this.operations.create(this.buildCreatePayload()), 'Операция создана');
  }

  private send(request$: Observable<unknown>, successMessage: string): void {
    this.saving.set(true);
    this.serverError.set(null);

    request$
      .pipe(
        finalize(() => this.saving.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: () => {
          this.visible.set(false);
          this.notifications.success(successMessage);
          this.saved.emit();
        },
        error: (error: unknown) => this.handleError(error),
      });
  }

  private handleError(error: unknown): void {
    const apiError = mapHttpError(error);
    this.serverError.set(apiError.message);

    if (apiError.code === 'VALIDATION_ERROR') {
      this.applyFieldErrors(apiError);
      return;
    }

    if (apiError.code === 'INSUFFICIENT_QUANTITY') {
      this.form.controls.quantity.setErrors({
        ...(this.form.controls.quantity.errors ?? {}),
        insufficient: true,
      });
    }
  }

  private applyFieldErrors(apiError: ApiError): void {
    for (const fieldError of validationErrors(apiError)) {
      const control = this.form.get(formFieldName(fieldError.field));
      if (!control) {
        continue;
      }

      control.setErrors({ ...(control.errors ?? {}), server: 'Проверьте значение поля.' });
      control.markAsTouched();
    }
  }

  private buildCreatePayload(): OperationCreateIn {
    return {
      asset_id: this.asset().id,
      ...this.buildCommonPayload(),
    };
  }

  private buildUpdatePayload(): OperationUpdateIn {
    const current = this.buildCommonPayload();
    const original = this.original;
    const payload: OperationUpdateIn = {};

    if (!original) {
      return current;
    }

    if (current.type !== original.type) {
      payload.type = current.type;
    }
    if (current.trade_date !== original.trade_date) {
      payload.trade_date = current.trade_date;
    }
    if (current.quantity !== original.quantity) {
      payload.quantity = current.quantity;
    }
    if (current.price !== original.price) {
      payload.price = current.price;
    }
    if (current.price_type !== original.price_type) {
      payload.price_type = current.price_type;
    }
    if (current.note !== original.note) {
      payload.note = current.note;
    }

    return payload;
  }

  private buildCommonPayload(): {
    type: OperationType;
    trade_date: string;
    quantity: number;
    price: string;
    price_type: PriceType;
    note: string | null;
  } {
    const raw = this.form.getRawValue();
    const trimmedNote = raw.note.trim();

    return {
      type: raw.type,
      // The form is valid at this point, so the date and quantity are present.
      trade_date: toIsoDate(raw.trade_date) ?? '',
      quantity: Number(raw.quantity.trim()),
      price: trimDecimalZeros(raw.price),
      price_type: this.isBond() ? raw.price_type : 'RUB',
      note: trimmedNote.length > 0 ? trimmedNote : null,
    };
  }

  private resetForm(): void {
    const operation = this.operation();
    const asset = this.asset();
    const priceType: PriceType =
      asset.type === 'BOND'
        ? (operation?.input_price_type ?? 'PERCENT')
        : 'RUB';

    this.form.reset({
      type: operation?.type ?? 'BUY',
      trade_date: operation ? isoToDate(operation.trade_date) : new Date(),
      quantity: operation ? String(operation.quantity) : '',
      price: operation ? trimDecimalZeros(operation.input_price) : '',
      price_type: priceType,
      note: operation?.note ?? '',
    });

    this.original = operation
      ? {
          type: operation.type,
          trade_date: operation.trade_date,
          quantity: operation.quantity,
          price: trimDecimalZeros(operation.input_price),
          price_type: operation.input_price_type,
          note: operation.note,
        }
      : null;

    this.submitted.set(false);
    this.serverError.set(null);
  }
}
