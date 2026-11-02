import {
  AfterViewInit,
  Directive,
  ElementRef,
  OnChanges,
  inject,
  input,
} from '@angular/core';

/**
 * Put `aria-describedby`/`aria-invalid` on the native input rendered by a
 * PrimeNG component (datepicker, select, etc.).
 *
 * PrimeNG exposes no public inputs for these attributes on every component, so
 * the directive resolves the inner focusable input from the host element.
 */
@Directive({
  selector: '[appAriaDescribedBy]',
  standalone: true,
})
export class AriaDescribedByDirective implements AfterViewInit, OnChanges {
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly appAriaDescribedBy = input<string | null>(null);
  readonly appAriaInvalid = input<boolean>(false);

  ngAfterViewInit(): void {
    this.apply();
  }

  ngOnChanges(): void {
    this.apply();
  }

  private apply(): void {
    const input = this.resolveInput();
    if (!input) {
      return;
    }

    const describedBy = this.appAriaDescribedBy();
    if (describedBy) {
      input.setAttribute('aria-describedby', describedBy);
    } else {
      input.removeAttribute('aria-describedby');
    }

    if (this.appAriaInvalid()) {
      input.setAttribute('aria-invalid', 'true');
    } else {
      input.removeAttribute('aria-invalid');
    }
  }

  private resolveInput(): HTMLInputElement | null {
    const element = this.host.nativeElement;
    if (element instanceof HTMLInputElement) {
      return element;
    }

    return element.querySelector('input');
  }
}
