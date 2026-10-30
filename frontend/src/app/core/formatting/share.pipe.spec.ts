import { SharePipe } from './share.pipe';

function normalize(value: string): string {
  return value.replace(/[\u00a0\u202f]/g, ' ');
}

describe('SharePipe', () => {
  const pipe = new SharePipe();

  it('returns the empty placeholder for empty values', () => {
    expect(pipe.transform(null)).toBe('—');
    expect(pipe.transform(undefined)).toBe('—');
    expect(pipe.transform('')).toBe('—');
  });

  it('converts a portfolio ratio to a percentage for display', () => {
    expect(normalize(pipe.transform('0.2789'))).toBe('27,89 %');
    expect(normalize(pipe.transform('0.7211'))).toBe('72,11 %');
    expect(normalize(pipe.transform('0.5'))).toBe('50,00 %');
  });

  it('returns the empty placeholder for invalid input', () => {
    expect(pipe.transform('oops')).toBe('—');
  });
});
