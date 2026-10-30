import { PricePipe } from './price.pipe';

function normalize(value: string): string {
  return value.replace(/[\u00a0\u202f]/g, ' ');
}

describe('PricePipe', () => {
  const pipe = new PricePipe();

  it('returns the empty placeholder for empty values', () => {
    expect(pipe.transform(null)).toBe('—');
    expect(pipe.transform(undefined)).toBe('—');
    expect(pipe.transform('')).toBe('—');
  });

  it('shows at least two decimals', () => {
    expect(normalize(pipe.transform('302.000000'))).toBe('302,00');
    expect(normalize(pipe.transform('5'))).toBe('5,00');
  });

  it('trims trailing zeros but keeps up to six decimals', () => {
    expect(normalize(pipe.transform('302.123400'))).toBe('302,1234');
    expect(normalize(pipe.transform('302.123456'))).toBe('302,123456');
    expect(normalize(pipe.transform('97.600000'))).toBe('97,60');
  });

  it('returns the empty placeholder for invalid input', () => {
    expect(pipe.transform('oops')).toBe('—');
  });
});
