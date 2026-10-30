import { Pipe, PipeTransform } from '@angular/core';

import { EMPTY_TEXT, emptyOrNumber } from './number-input';

const SHARE = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

/**
 * Formats an API portfolio ratio (`"0.2789"`) as a percentage (`27,89 %`).
 *
 * Display-only conversion: the backend owns the ratio calculation.
 */
@Pipe({
  name: 'share',
  standalone: true,
  pure: true,
})
export class SharePipe implements PipeTransform {
  transform(value: string | number | null | undefined): string {
    const ratio = emptyOrNumber(value);
    return ratio === null ? EMPTY_TEXT : `${SHARE.format(ratio * 100)} %`;
  }
}
