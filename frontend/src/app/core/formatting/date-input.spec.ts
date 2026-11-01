import { isoToDate, toIsoDate } from './date-input';

describe('date input conversion', () => {
  it('formats a local Date as YYYY-MM-DD without timezone math', () => {
    expect(toIsoDate(new Date(2026, 9, 30))).toBe('2026-10-30');
    expect(toIsoDate(new Date(2026, 0, 1))).toBe('2026-01-01');
  });

  it('returns null for missing or invalid dates', () => {
    expect(toIsoDate(null)).toBeNull();
    expect(toIsoDate(new Date('invalid'))).toBeNull();
  });

  it('parses YYYY-MM-DD as a local date', () => {
    const date = isoToDate('2026-10-30');

    expect(date?.getFullYear()).toBe(2026);
    expect(date?.getMonth()).toBe(9);
    expect(date?.getDate()).toBe(30);
    expect(date?.getHours()).toBe(0);
  });

  it('rejects malformed and impossible dates', () => {
    expect(isoToDate('30.10.2026')).toBeNull();
    expect(isoToDate('2026-02-31')).toBeNull();
    expect(isoToDate(null)).toBeNull();
  });
});
