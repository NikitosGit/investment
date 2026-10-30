import { Pipe, PipeTransform } from '@angular/core';

import { EMPTY_TEXT, emptyOrNumber } from './number-input';

const PERCENT = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 6,
});

/**
 * Formats an API percentage string (e.g. `"95.123000"`) as `95,123 %`.
 *
 * The value is already a percentage (`PriceType.PERCENT`, coupon rates).
 * For portfolio ratios (`0.2789`) use `SharePipe`.
 */
@Pipe({
  name: 'percent',
  standalone: true,
  pure: true,
})
export class PercentPipe implements PipeTransform {
  transform(value: string | number | null | undefined): string {
    const percent = emptyOrNumber(value);
    return percent === null ? EMPTY_TEXT : `${PERCENT.format(percent)} %`;
  }
}
