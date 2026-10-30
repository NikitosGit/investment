import { TestBed } from '@angular/core/testing';

import { EmptyStateComponent } from './empty-state.component';

describe('EmptyStateComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [EmptyStateComponent] }).compileComponents();
  });

  it('renders title, message and icon', () => {
    const fixture = TestBed.createComponent(EmptyStateComponent);
    fixture.componentRef.setInput('title', 'Портфель пуст');
    fixture.componentRef.setInput('message', 'Добавьте первый актив');
    fixture.componentRef.setInput('icon', 'pi pi-briefcase');
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Портфель пуст');
    expect(element.textContent).toContain('Добавьте первый актив');
    expect(element.querySelector('.empty-state__icon')?.classList).toContain('pi-briefcase');
  });
});
