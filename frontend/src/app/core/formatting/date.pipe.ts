import { Pipe, PipeTransform } from '@angular/core';

import { EMPTY_TEXT } from './number-input';

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

/**
 * Normalize ISO fractions longer than milliseconds (`...12.092327Z`), which
 * some browsers parse inconsistently.
 */
const LONG_FRACTION = /(\.\d{3})\d+/;

/**
 * Formats API dates without timezone math:
 *
 * * `YYYY-MM-DD`    -> `dd.MM.yyyy`
 * * ISO date-time   -> `dd.MM.yyyy HH:mm` in the browser's local zone
 * * `null`/empty    -> `—`
 */
@Pipe({
  name: 'date',
  standalone: true,
  pure: true,
})
export class DatePipe implements PipeTransform {
  transform(value: string | Date | null | undefined): string {
    if (value === null || value === undefined) {
      return EMPTY_TEXT;
    }

    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (trimmed.length === 0) {
        return EMPTY_TEXT;
      }

      const dateOnly = DATE_ONLY.exec(trimmed);
      if (dateOnly) {
        return `${dateOnly[3]}.${dateOnly[2]}.${dateOnly[1]}`;
      }

      return this.formatDate(new Date(trimmed.replace(LONG_FRACTION, '$1')), true);
    }

    return this.formatDate(value, value.getHours() !== 0 || value.getMinutes() !== 0);
  }

  private formatDate(date: Date, withTime: boolean): string {
    if (Number.isNaN(date.getTime())) {
      return EMPTY_TEXT;
    }

    const day = pad(date.getDate());
    const month = pad(date.getMonth() + 1);
    const year = date.getFullYear();
    const result = `${day}.${month}.${year}`;

    if (!withTime) {
      return result;
    }

    return `${result} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }
}

function pad(value: number): string {
  return value.toString().padStart(2, '0');
}
