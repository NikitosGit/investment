/** Placeholder shown for missing or invalid values. */
export const EMPTY_TEXT = '—';

/**
 * Convert an API numeric string or number into a finite number for display.
 *
 * This conversion is for `Intl.NumberFormat` only — never for arithmetic.
 */
export function emptyOrNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === 'string' && value.trim().length === 0) {
    return null;
  }

  const parsed = typeof value === 'number' ? value : Number(value.trim());
  return Number.isFinite(parsed) ? parsed : null;
}
