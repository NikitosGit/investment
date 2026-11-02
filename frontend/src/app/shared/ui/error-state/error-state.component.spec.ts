import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import Aura from '@primeuix/themes/aura';
import { providePrimeNG } from 'primeng/config';

import { ErrorStateComponent } from './error-state.component';

describe('ErrorStateComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ErrorStateComponent],
      providers: [
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
      ],
    }).compileComponents();
  });

  it('renders the message and emits retry', () => {
    const fixture = TestBed.createComponent(ErrorStateComponent);
    fixture.componentRef.setInput('message', 'Нет связи с сервером');
    fixture.detectChanges();

    let retried = 0;
    fixture.componentInstance.retry.subscribe(() => retried++);

    const element = fixture.nativeElement as HTMLElement;
    expect(element.getAttribute('role')).toBeNull();
    expect(element.textContent).toContain('Нет связи с сервером');
    expect(element.querySelector('[role="alert"]')).toBeTruthy();

    fixture.debugElement.query(By.css('button')).nativeElement.click();

    expect(retried).toBe(1);
  });
});
