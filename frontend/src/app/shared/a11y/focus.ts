import type { FormGroup } from '@angular/forms';

/**
 * Remember the element that had focus before a dialog opened so it can be
 * restored when the dialog closes.
 */
export function rememberActiveElement(doc: Document = document): HTMLElement | null {
  const active = doc.activeElement;
  return active instanceof HTMLElement ? active : null;
}

/** Return focus to a previously remembered element if it is still in the DOM. */
export function restoreFocus(element: HTMLElement | null): void {
  if (element?.isConnected) {
    element.focus();
  }
}

/**
 * Move focus to the first invalid control of a form.
 *
 * `elementIds` maps a control name to the DOM id of its focusable element
 * (input, PrimeNG select combobox or datepicker input), in visual order.
 */
export function focusFirstInvalidField(
  form: FormGroup,
  elementIds: Readonly<Partial<Record<string, string>>>,
  doc: Document = document,
): boolean {
  for (const name of Object.keys(form.controls)) {
    if (!form.controls[name].invalid) {
      continue;
    }

    const id = elementIds[name];
    if (!id) {
      continue;
    }

    const element = doc.getElementById(id);
    if (element) {
      element.focus();
      return true;
    }
  }

  return false;
}
