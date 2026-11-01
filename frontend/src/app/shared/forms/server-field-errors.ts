import type { FormGroup } from '@angular/forms';

import type { ApiError } from '../../core/api/api-error';
import { formFieldName, validationErrors } from '../../core/api/api-error';

export interface ServerFieldErrorOptions {
  /** Use the backend message on the control (default: `true`). */
  useBackendMessage?: boolean;
  /** Message used for a field error without a usable backend text. */
  fallbackMessage?: string;
}

/**
 * Map `422` field errors (`details.errors[]`) from the API envelope onto form
 * controls. Unknown fields are ignored and existing control errors are kept.
 */
export function applyServerFieldErrors(
  form: FormGroup,
  apiError: ApiError,
  options: ServerFieldErrorOptions = {},
): void {
  const useBackendMessage = options.useBackendMessage ?? true;
  const fallbackMessage = options.fallbackMessage ?? 'Проверьте значение поля.';

  for (const fieldError of validationErrors(apiError)) {
    const control = form.get(formFieldName(fieldError.field));
    if (!control) {
      continue;
    }

    const message =
      useBackendMessage && fieldError.message ? fieldError.message : fallbackMessage;

    control.setErrors({
      ...(control.errors ?? {}),
      server: message,
    });
    control.markAsTouched();
  }
}
