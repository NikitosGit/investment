import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';

import type { Period } from '../../../core/api/models';
import { PeriodSwitcherComponent } from './period-switcher.component';

describe('PeriodSwitcherComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [PeriodSwitcherComponent] }).compileComponents();
  });

  function button(fixture: ComponentFixture<PeriodSwitcherComponent>, label: string) {
    return fixture.debugElement
      .queryAll(By.css('button'))
      .map((element) => element.nativeElement as HTMLButtonElement)
      .find((element) => element.textContent?.trim() === label);
  }

  it('renders all periods and marks the selected one', () => {
    const fixture = TestBed.createComponent(PeriodSwitcherComponent);
    fixture.componentRef.setInput('selected', '1Y');
    fixture.detectChanges();

    const buttons = fixture.debugElement
      .queryAll(By.css('button'))
      .map((element) => element.nativeElement as HTMLButtonElement);

    expect(buttons.map((element) => element.textContent?.trim())).toEqual([
      '1 мес.',
      '3 мес.',
      '1 год',
      'Все',
    ]);
    expect(button(fixture, '1 год')?.getAttribute('aria-pressed')).toBe('true');
    expect(button(fixture, '1 мес.')?.classList).not.toContain('is-active');
  });

  it('emits a change only for a different period', () => {
    const fixture = TestBed.createComponent(PeriodSwitcherComponent);
    fixture.componentRef.setInput('selected', '1Y');
    fixture.detectChanges();

    const emitted: Period[] = [];
    fixture.componentInstance.change.subscribe((period) => emitted.push(period));

    button(fixture, '3 мес.')?.click();
    button(fixture, '1 год')?.click();

    expect(emitted).toEqual(['3M']);
  });
});
