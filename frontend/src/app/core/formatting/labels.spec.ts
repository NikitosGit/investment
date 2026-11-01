import {
  assetTypeLabel,
  dataSourceLabel,
  incomeKindLabel,
  incomeStatusLabel,
  operationTypeLabel,
} from './labels';

describe('Russian domain labels', () => {
  it('labels asset types', () => {
    expect(assetTypeLabel('STOCK')).toBe('Акция');
    expect(assetTypeLabel('BOND')).toBe('Облигация');
  });

  it('labels operation types', () => {
    expect(operationTypeLabel('BUY')).toBe('Покупка');
    expect(operationTypeLabel('SELL')).toBe('Продажа');
  });

  it('labels income kinds and statuses', () => {
    expect(incomeKindLabel('DIVIDEND')).toBe('Дивиденд');
    expect(incomeKindLabel('COUPON')).toBe('Купон');
    expect(incomeStatusLabel('PAID')).toBe('Выплачено');
    expect(incomeStatusLabel('EXPECTED')).toBe('Ожидается');
  });

  it('labels data sources', () => {
    expect(dataSourceLabel('MOEX')).toBe('MOEX');
    expect(dataSourceLabel('MANUAL')).toBe('Вручную');
  });
});
