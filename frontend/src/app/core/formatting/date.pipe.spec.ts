import { DatePipe } from './date.pipe';

function localDateTime(date: Date): string {
  const pad = (value: number): string => value.toString().padStart(2, '0');
  return (
    `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

describe('DatePipe', () => {
  const pipe = new DatePipe();

  it('returns the empty placeholder for empty values', () => {
    expect(pipe.transform(null)).toBe('—');
    expect(pipe.transform(undefined)).toBe('—');
    expect(pipe.transform('')).toBe('—');
  });

  it('formats a date-only string without timezone shifts', () => {
    expect(pipe.transform('2026-10-30')).toBe('30.10.2026');
    expect(pipe.transform('2026-01-05')).toBe('05.01.2026');
  });

  it('formats a local ISO date-time exactly', () => {
    expect(pipe.transform('2026-10-30T15:10:00')).toBe('30.10.2026 15:10');
  });

  it('normalizes fractions longer than milliseconds', () => {
    expect(pipe.transform('2026-10-30T15:10:12.092327')).toBe('30.10.2026 15:10');
    expect(pipe.transform('2026-10-30T15:10:12.092327Z')).toBe(
      pipe.transform('2026-10-30T15:10:12.092Z'),
    );
  });

  it('honours an explicit +03:00 offset when converting to local time', () => {
    const expected = localDateTime(new Date('2026-10-30T15:10:12.092+03:00'));
    expect(pipe.transform('2026-10-30T15:10:12.092327+03:00')).toBe(expected);
  });

  it('formats Date objects, adding time only when it is set', () => {
    expect(pipe.transform(new Date(2026, 9, 30))).toBe('30.10.2026');
    expect(pipe.transform(new Date(2026, 9, 30, 15, 10))).toBe('30.10.2026 15:10');
  });

  it('returns the empty placeholder for invalid input', () => {
    expect(pipe.transform('not-a-date')).toBe('—');
  });
});
