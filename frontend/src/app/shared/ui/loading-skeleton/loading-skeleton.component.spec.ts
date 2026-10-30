import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import Aura from '@primeuix/themes/aura';
import { providePrimeNG } from 'primeng/config';

import { LoadingSkeletonComponent } from './loading-skeleton.component';

describe('LoadingSkeletonComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LoadingSkeletonComponent],
      providers: [
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
      ],
    }).compileComponents();
  });

  it('renders the requested number of rows', () => {
    const fixture = TestBed.createComponent(LoadingSkeletonComponent);
    fixture.componentRef.setInput('rows', 2);
    fixture.componentRef.setInput('cards', 0);
    fixture.detectChanges();

    expect(fixture.debugElement.queryAll(By.css('p-skeleton')).length).toBe(2);
  });

  it('renders three skeleton lines per card', () => {
    const fixture = TestBed.createComponent(LoadingSkeletonComponent);
    fixture.componentRef.setInput('rows', 0);
    fixture.componentRef.setInput('cards', 2);
    fixture.detectChanges();

    expect(fixture.debugElement.queryAll(By.css('p-skeleton')).length).toBe(6);
  });
});
