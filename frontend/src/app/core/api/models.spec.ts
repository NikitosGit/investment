import { toPeriod, toPriceSource } from './models';

describe('API model guards', () => {
  describe('toPeriod', () => {
    it('accepts every supported dashboard period', () => {
      expect(toPeriod('1M')).toBe('1M');
      expect(toPeriod('3M')).toBe('3M');
      expect(toPeriod('1Y')).toBe('1Y');
      expect(toPeriod('ALL')).toBe('ALL');
    });

    it('rejects unknown and missing values instead of casting them', () => {
      expect(toPeriod('2Y')).toBeNull();
      expect(toPeriod('1y')).toBeNull();
      expect(toPeriod('')).toBeNull();
      expect(toPeriod(null)).toBeNull();
      expect(toPeriod(undefined)).toBeNull();
    });
  });

  describe('toPriceSource', () => {
    it('accepts the known price sources', () => {
      expect(toPriceSource('MOEX')).toBe('MOEX');
      expect(toPriceSource('MANUAL')).toBe('MANUAL');
      expect(toPriceSource('COST')).toBe('COST');
    });

    it('returns an empty fallback for unknown or missing values', () => {
      expect(toPriceSource('BROKER')).toBe('');
      expect(toPriceSource(null)).toBe('');
      expect(toPriceSource(undefined)).toBe('');
    });
  });
});
