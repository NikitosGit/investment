import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';

import { AriaDescribedByDirective } from './aria-described-by.directive';

@Component({
  standalone: true,
  imports: [AriaDescribedByDirective],
  template: `
    <div appAriaDescribedBy="hint-id" [appAriaInvalid]="invalid">
      <input id="inner" />
    </div>
  `,
})
class HostComponent {
  invalid = false;
}

describe('AriaDescribedByDirective', () => {
  it('applies describedby and invalid to the inner input', () => {
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('#inner') as HTMLInputElement;
    expect(input.getAttribute('aria-describedby')).toBe('hint-id');
    expect(input.hasAttribute('aria-invalid')).toBeFalse();

    fixture.componentInstance.invalid = true;
    fixture.detectChanges();

    expect(input.getAttribute('aria-invalid')).toBe('true');
  });
});
