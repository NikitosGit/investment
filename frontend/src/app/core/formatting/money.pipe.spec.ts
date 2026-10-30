import { MoneyPipe } from './money.pipe';

function normalize(value: string): string {
  return value.replace(/[\u00a0\u202f]/g, ' ');
}

describe('MoneyPipe', () => {
  const pipe = new MoneyPipe();

  it('returns the empty placeholder for null, undefined and empty input', () => {
    expect(pipe.transform(null)).toBe('—');
    expect(pipe.transform(undefined)).toBe('—');
    expect(pipe.transform('')).toBe('—');
    expect(pipe.transform('   ')).toBe('—');
  });

  it('formats an integer string as rubles', () => {
    expect(normalize(pipe.transform('16242'))).toBe('16 242,00 ₽');
  });

  it('formats a decimal string with two digits', () => {
    expect(normalize(pipe.transform('16242.50'))).toBe('16 242,50 ₽');
    expect(normalize(pipe.transform('0.00'))).toBe('0,00 ₽');
  });

  it('formats a numeric input', () => {
    expect(normalize(pipe.transform(15918.45))).toBe('15 918,45 ₽');
  });

  it('returns the empty placeholder for invalid input', () => {
    expect(pipe.transform('not-a-number')).toBe('—');
  });
});
