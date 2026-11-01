import type { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';

const INTEGER_INPUT = /^\d+$/;
const DECIMAL_INPUT = /^\d+(?:[.,]\d+)?$/;
const MAX_SAFE_QUANTITY = 1_000_000_000;

/** Normalize a user-entered decimal for the API: `12,5` -> `"12.5"`. */
export function normalizeDecimalInput(value: string | number): string {
  return String(value).trim().replace(',', '.');
}

/**
 * Normalize a decimal and drop insignificant trailing zeros.
 *
 * This is display/string cleanup only; the numeric value never changes and no
 * arithmetic is performed.
 */
export function trimDecimalZeros(value: string | number): string {
  const normalized = normalizeDecimalInput(value);
  return normalized.includes('.')
    ? normalized.replace(/0+$/, '').replace(/\.$/, '')
    : normalized;
}

/** Require a whole number greater than zero (quantity). */
export function positiveIntegerValidator(control: AbstractControl): ValidationErrors | null {
  const value = String(control.value ?? '').trim();

  if (!INTEGER_INPUT.test(value)) {
    return { positiveInteger: true };
  }

  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed <= 0 || parsed > MAX_SAFE_QUANTITY) {
    return { positiveInteger: true };
  }

  return null;
}

/**
 * Allow an empty value or a non-negative whole number (quantity).
 *
 * An empty control stays valid so optional API fields can be omitted; callers
 * that require a value add `Validators.required` on top.
 */
export function nonNegativeIntegerValidator(control: AbstractControl): ValidationErrors | null {
  const value = String(control.value ?? '').trim();

  if (value.length === 0) {
    return null;
  }

  if (!INTEGER_INPUT.test(value)) {
    return { nonNegativeInteger: true };
  }

  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0 || parsed > MAX_SAFE_QUANTITY) {
    return { nonNegativeInteger: true };
  }

  return null;
}

/**
 * Require a positive decimal with at most `maxDecimals` fraction digits.
 *
 * Accepts both `.` and `,` as the decimal separator and never converts the
 * value for arithmetic; the raw string is sent to the API.
 */
export function positiveDecimalValidator(maxDecimals = 6): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const value = String(control.value ?? '').trim();

    if (!DECIMAL_INPUT.test(value)) {
      return { positiveDecimal: true };
    }

    const fraction = value.split(/[.,]/)[1] ?? '';
    if (fraction.length > maxDecimals) {
      return { positiveDecimal: true };
    }

    return Number(normalizeDecimalInput(value)) > 0 ? null : { positiveDecimal: true };
  };
}

/** Allow an empty value or a positive decimal with at most `maxDecimals`. */
export function optionalPositiveDecimalValidator(maxDecimals = 6): ValidatorFn {
  const validator = positiveDecimalValidator(maxDecimals);

  return (control: AbstractControl): ValidationErrors | null => {
    const value = String(control.value ?? '').trim();
    return value.length === 0 ? null : validator(control);
  };
}
