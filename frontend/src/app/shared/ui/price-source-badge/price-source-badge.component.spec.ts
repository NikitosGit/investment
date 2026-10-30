import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import Aura from '@primeuix/themes/aura';
import { providePrimeNG } from 'primeng/config';

import type { PriceSource } from '../../../core/api/models';
import { PriceSourceBadgeComponent } from './price-source-badge.component';

describe('PriceSourceBadgeComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PriceSourceBadgeComponent],
      providers: [
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
      ],
    }).compileComponents();
  });

  function create(source: PriceSource): ComponentFixture<PriceSourceBadgeComponent> {
    const fixture = TestBed.createComponent(PriceSourceBadgeComponent);
    fixture.componentRef.setInput('source', source);
    fixture.detectChanges();
    return fixture;
  }

  it('maps MOEX prices', () => {
    const fixture = create('MOEX');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('MOEX');
  });

  it('maps manually entered prices', () => {
    const fixture = create('MANUAL');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Вручную');
  });

  it('maps cost-basis fallback and stale state', () => {
    const fixture = create('COST');
    fixture.componentRef.setInput('isStale', true);
    fixture.componentRef.setInput('priceDate', '2026-10-29');
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('Себестоимость');
    expect(text).toContain('Устарело');
    expect(text).toContain('29.10.2026');
  });
});
