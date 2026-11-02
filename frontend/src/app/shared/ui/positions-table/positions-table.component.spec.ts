import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import Aura from '@primeuix/themes/aura';
import { providePrimeNG } from 'primeng/config';

import type { PositionItem } from '../../../core/api/models';
import { PositionsTableComponent } from './positions-table.component';

const POSITIONS: PositionItem[] = [
  {
    asset: { id: 1, secid: 'SBER', name: 'Сбербанк', type: 'STOCK' },
    quantity: 15,
    avg_price: '110.000000',
    avg_price_percent: null,
    current_price: '302.000000',
    current_price_type: 'RUB',
    current_face_value: null,
    market_value: '4530.00',
    invested: '1650.00',
    share: '0.2789',
    price_date: '2026-10-30',
    price_source: 'MANUAL',
    is_stale: true,
  },
  {
    asset: { id: 2, secid: 'SU26238RMFS4', name: 'ОФЗ 26238', type: 'BOND' },
    quantity: 15,
    avg_price: '951.230000',
    avg_price_percent: '95.123000',
    current_price: '97.600000',
    current_price_type: 'PERCENT',
    current_face_value: '800.00',
    market_value: '11712.00',
    invested: '14268.45',
    share: '0.7211',
    price_date: '2026-10-30',
    price_source: 'MOEX',
    is_stale: false,
  },
];

function normalize(value: string): string {
  return value.replace(/[\u00a0\u202f]/g, ' ');
}

describe('PositionsTableComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PositionsTableComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
      ],
    }).compileComponents();
  });

  function create(): ComponentFixture<PositionsTableComponent> {
    const fixture = TestBed.createComponent(PositionsTableComponent);
    fixture.componentRef.setInput('positions', POSITIONS);
    fixture.detectChanges();
    return fixture;
  }

  it('renders both position types with API prices and shares', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;
    const content = normalize(element.textContent ?? '');

    expect(element.querySelectorAll('p-table tbody tr').length).toBe(2);
    expect(content).toContain('SBER');
    expect(content).toContain('SU26238RMFS4');
    expect(content).toContain('Акция');
    expect(content).toContain('Облигация');
    expect(content).toContain('110,00 ₽');
    expect(content).toContain('302,00 ₽');
    expect(content).toContain('95,123 %');
    expect(content).toContain('97,60 %');
    expect(content).toContain('4 530,00 ₽');
    expect(content).toContain('27,89 %');
    expect(content).toContain('72,11 %');
  });

  it('links each row to the asset card and shows the price source', () => {
    const fixture = create();
    const element = fixture.nativeElement as HTMLElement;

    expect(
      Array.from(element.querySelectorAll<HTMLAnchorElement>('[data-position-link]')).map((link) =>
        link.getAttribute('href'),
      ),
    ).toEqual(['/assets/1', '/assets/2']);

    expect(normalize(element.textContent ?? '')).toContain('Вручную');
    expect(normalize(element.textContent ?? '')).toContain('Устарело');
    expect(normalize(element.textContent ?? '')).toContain('MOEX');
  });

  it('has an accessible name for the table', () => {
    const fixture = create();
    const table = fixture.nativeElement.querySelector('table') as HTMLTableElement;

    expect(table.getAttribute('aria-label')).toBe('Открытые позиции портфеля');
  });
});
