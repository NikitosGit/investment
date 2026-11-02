import { FormControl, FormGroup, Validators } from '@angular/forms';

import { focusFirstInvalidField, rememberActiveElement, restoreFocus } from './focus';

describe('focus helpers', () => {
  let root: HTMLElement;

  beforeEach(() => {
    root = document.createElement('div');
    root.id = 'focus-test-root';
    document.body.appendChild(root);
  });

  afterEach(() => {
    root.remove();
  });

  it('focuses the first invalid field in form order', () => {
    const form = new FormGroup({
      first: new FormControl('', Validators.required),
      second: new FormControl('', Validators.required),
    });

    const first = document.createElement('input');
    first.id = 'field-first';
    const second = document.createElement('input');
    second.id = 'field-second';
    root.append(first, second);

    expect(focusFirstInvalidField(form, { first: 'field-first', second: 'field-second' })).toBeTrue();
    expect(document.activeElement).toBe(first);
  });

  it('does nothing when the form is valid or the target is missing', () => {
    const form = new FormGroup({ first: new FormControl('ok') });

    expect(focusFirstInvalidField(form, { first: 'field-first' })).toBeFalse();

    form.controls.first.setValidators(Validators.required);
    form.controls.first.updateValueAndValidity();

    expect(focusFirstInvalidField(form, { first: 'missing' })).toBeFalse();
  });

  it('skips invalid controls without a focusable id', () => {
    const form = new FormGroup({
      withoutId: new FormControl('', Validators.required),
      withId: new FormControl('', Validators.required),
    });

    const target = document.createElement('input');
    target.id = 'field-with-id';
    root.appendChild(target);

    expect(
      focusFirstInvalidField(form, { withoutId: undefined, withId: 'field-with-id' }),
    ).toBeTrue();
    expect(document.activeElement).toBe(target);
  });

  it('remembers and restores the active element only while it is connected', () => {
    const trigger = document.createElement('button');
    const other = document.createElement('button');
    root.append(trigger, other);

    trigger.focus();
    expect(rememberActiveElement()).toBe(trigger);

    other.focus();
    restoreFocus(trigger);
    expect(document.activeElement).toBe(trigger);

    trigger.remove();
    other.focus();
    restoreFocus(trigger);
    expect(document.activeElement).toBe(other);
  });
});
