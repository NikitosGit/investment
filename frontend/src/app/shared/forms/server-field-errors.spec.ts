import { FormControl, FormGroup } from '@angular/forms';

import { ApiError } from '../../core/api/api-error';
import { applyServerFieldErrors } from './server-field-errors';

function makeForm(): FormGroup {
  return new FormGroup({
    amount_total: new FormControl(''),
    note: new FormControl(''),
  });
}

function validationError(): ApiError {
  return new ApiError(422, 'VALIDATION_ERROR', 'Ошибка валидации данных', {
    errors: [
      {
        field: 'body.amount_total',
        message: 'Input should be greater than 0',
        type: 'greater_than',
      },
      {
        field: 'body.unknown_field',
        message: 'Unknown field error',
        type: 'value_error',
      },
    ],
  });
}

describe('applyServerFieldErrors', () => {
  it('maps prefixed backend fields and keeps existing control errors', () => {
    const form = makeForm();
    form.controls['amount_total'].setErrors({ custom: true });

    applyServerFieldErrors(form, validationError());

    expect(form.controls['amount_total'].errors).toEqual({
      custom: true,
      server: 'Input should be greater than 0',
    });
    expect(form.controls['amount_total'].touched).toBeTrue();
    expect(form.controls['note'].errors).toBeNull();
  });

  it('can use a generic message instead of the backend text', () => {
    const form = makeForm();

    applyServerFieldErrors(form, validationError(), { useBackendMessage: false });

    expect(form.controls['amount_total'].errors?.['server']).toBe(
      'Проверьте значение поля.',
    );
  });

  it('ignores payloads without structured field errors', () => {
    const form = makeForm();
    const error = new ApiError(422, 'VALIDATION_ERROR', 'Ошибка валидации данных');

    expect(() => applyServerFieldErrors(form, error)).not.toThrow();
    expect(form.controls['amount_total'].errors).toBeNull();
  });
});
