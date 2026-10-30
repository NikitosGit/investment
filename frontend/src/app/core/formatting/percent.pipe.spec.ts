import { PercentPipe } from './percent.pipe';

function normalize(value: string): string {
  return value.replace(/[\u00a0\u202f]/g, ' ');
}

describe('PercentPipe', () => {
  const pipe = new PercentPipe();

  it('returns the empty placeholder for empty values', () => {
    expect(pipe.transform(null)).toBe('—');
    expect(pipe.transform(undefined)).toBe('—');
    expect(pipe.transform('')).toBe('—');
  });

  it('formats a coupon percent with three decimals', () => {
    expect(normalize(pipe.transform('95.123000'))).toBe('95,123 %');
  });

  it('keeps up to six decimals and drops trailing zeros', () => {
    expect(normalize(pipe.transform('27.890000'))).toBe('27,89 %');
    expect(normalize(pipe.transform('12.5'))).toBe('12,5 %');
  });

  it('formats an integer without decimals', () => {
    expect(normalize(pipe.transform('5'))).toBe('5 %');
  });

  it('returns the empty placeholder for invalid input', () => {
    expect(pipe.transform('nope')).toBe('—');
  });
});
