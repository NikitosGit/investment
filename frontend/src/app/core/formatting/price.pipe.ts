import { Pipe, PipeTransform } from '@angular/core';

import { EMPTY_TEXT, emptyOrNumber } from './number-input';

const PRICE = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 6,
});

/**
 * Formats an API price string (e.g. `"302.000000"`) with 2–6 decimals and no
 * currency symbol. Display only.
 */
@Pipe({
  name: 'price',
  standalone: true,
  pure: true,
})
export class PricePipe implements PipeTransform {
  transform(value: string | number | null | undefined): string {
    const price = emptyOrNumber(value);
    return price === null ? EMPTY_TEXT : PRICE.format(price);
  }
}
