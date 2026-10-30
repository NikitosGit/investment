import { TestBed } from '@angular/core/testing';

import { StatCardComponent } from './stat-card.component';

describe('StatCardComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [StatCardComponent] }).compileComponents();
  });

  it('renders label, value, hint, icon and severity styling', () => {
    const fixture = TestBed.createComponent(StatCardComponent);
    fixture.componentRef.setInput('label', 'Стоимость');
    fixture.componentRef.setInput('value', '16 242,00 ₽');
    fixture.componentRef.setInput('hint', 'На 30.10.2026');
    fixture.componentRef.setInput('icon', 'pi pi-wallet');
    fixture.componentRef.setInput('severity', 'success');
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;

    expect(element.textContent).toContain('Стоимость');
    expect(element.textContent).toContain('16 242,00 ₽');
    expect(element.textContent).toContain('На 30.10.2026');
    expect(element.querySelector('.stat-card')?.classList).toContain('stat-card--success');
    expect(element.querySelector('.stat-card__icon')?.classList).toContain('pi-wallet');
  });

  it('uses neutral styling by default', () => {
    const fixture = TestBed.createComponent(StatCardComponent);
    fixture.componentRef.setInput('label', 'Позиции');
    fixture.componentRef.setInput('value', '2');
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.stat-card')?.classList).toContain(
      'stat-card--neutral',
    );
  });
});
