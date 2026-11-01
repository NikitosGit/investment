import { FormControl } from '@angular/forms';

import {
  nonNegativeIntegerValidator,
  normalizeDecimalInput,
  optionalPositiveDecimalValidator,
  positiveDecimalValidator,
  positiveIntegerValidator,
  trimDecimalZeros,
} from './validators';

describe('positiveIntegerValidator', () => {
  it('accepts positive whole numbers', () => {
    for (const value of ['1', '15', 42]) {
      expect(positiveIntegerValidator(new FormControl(value))).toBeNull();
    }
  });

  it('rejects zero, negatives, fractions and junk', () => {
    for (const value of ['0', '-5', '1.5', 'abc', '', null]) {
      expect(positiveIntegerValidator(new FormControl(value))).not.toBeNull();
    }
  });
});

describe('nonNegativeIntegerValidator', () => {
  it('accepts zero, positive whole numbers and an empty optional value', () => {
    for (const value of ['0', '1', '15', 42, '', null]) {
      expect(nonNegativeIntegerValidator(new FormControl(value))).toBeNull();
    }
  });

  it('rejects negatives, fractions and junk', () => {
    for (const value of ['-5', '1.5', 'abc']) {
      expect(nonNegativeIntegerValidator(new FormControl(value))).not.toBeNull();
    }
  });
});

describe('optionalPositiveDecimalValidator', () => {
  const validate = optionalPositiveDecimalValidator(2);

  it('accepts an empty value and valid positive decimals', () => {
    for (const value of ['', null, '1', '0,5', '150.25']) {
      expect(validate(new FormControl(value))).toBeNull();
    }
  });

  it('rejects zero and too many decimals', () => {
    for (const value of ['0', '1.234']) {
      expect(validate(new FormControl(value))).not.toBeNull();
    }
  });
});

describe('positiveDecimalValidator', () => {
  const validate = positiveDecimalValidator(6);

  it('accepts positive decimals with a dot or comma', () => {
    for (const value of ['1', '0.5', '97.600', '97,6', '0,000001']) {
      expect(validate(new FormControl(value))).toBeNull();
    }
  });

  it('rejects zero, negatives, more than six decimals and junk', () => {
    for (const value of ['0', '-1', '1.2345678', '1,2345678', 'abc', '', null]) {
      expect(validate(new FormControl(value))).not.toBeNull();
    }
  });

  it('honours a smaller fraction limit', () => {
    expect(positiveDecimalValidator(2)(new FormControl('1.23'))).toBeNull();
    expect(positiveDecimalValidator(2)(new FormControl('1.234'))).not.toBeNull();
  });
});

describe('normalizeDecimalInput', () => {
  it('trims and normalizes the decimal separator', () => {
    expect(normalizeDecimalInput(' 97,6 ')).toBe('97.6');
    expect(normalizeDecimalInput('300')).toBe('300');
  });
});

describe('trimDecimalZeros', () => {
  it('drops insignificant trailing zeros without arithmetic', () => {
    expect(trimDecimalZeros('100.000000')).toBe('100');
    expect(trimDecimalZeros('97.600000')).toBe('97.6');
    expect(trimDecimalZeros('0.500000')).toBe('0.5');
    expect(trimDecimalZeros('300')).toBe('300');
  });
});
