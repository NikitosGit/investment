const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Format a local `Date` as `YYYY-MM-DD` without any timezone conversion. */
export function toIsoDate(value: Date | null | undefined): string | null {
  if (!value || Number.isNaN(value.getTime())) {
    return null;
  }

  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Parse an API `YYYY-MM-DD` date as a local `Date`.
 *
 * `new Date('YYYY-MM-DD')` parses as UTC and can shift the day in negative
 * timezones, so the parts are passed to the local constructor instead.
 */
export function isoToDate(value: string | null | undefined): Date | null {
  if (!value) {
    return null;
  }

  const match = ISO_DATE.exec(value.trim());
  if (!match) {
    return null;
  }

  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));

  // Reject impossible calendar dates such as 2026-02-31.
  if (
    date.getFullYear() !== Number(match[1]) ||
    date.getMonth() !== Number(match[2]) - 1 ||
    date.getDate() !== Number(match[3])
  ) {
    return null;
  }

  return date;
}
