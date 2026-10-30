import { Pipe, PipeTransform } from '@angular/core';

import { EMPTY_TEXT, emptyOrNumber } from './number-input';

const RUB = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Formats an API money string (e.g. `"16242.00"`) as `16 242,00 ₽`.
 *
 * Display only: the numeric conversion never feeds arithmetic.
 */
@Pipe({
  name: 'money',
  standalone: true,
  pure: true,
})
export class MoneyPipe implements PipeTransform {
  transform(value: string | number | null | undefined): string {
    const amount = emptyOrNumber(value);
    return amount === null ? EMPTY_TEXT : RUB.format(amount);
  }
}
