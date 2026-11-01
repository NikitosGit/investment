import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import Aura from '@primeuix/themes/aura';
import { providePrimeNG } from 'primeng/config';
import { Subject, of, throwError } from 'rxjs';

import { ApiError } from '../../../core/api/api-error';
import type {
  AssetDetail,
  AssetListItem,
  AssetSearchItem,
  AssetSearchResponse,
} from '../../../core/api/models';
import { AssetsService } from '../../../core/services/assets.service';
import { AssetSearchDialogComponent } from './asset-search-dialog.component';

const LOCAL_ASSET: AssetListItem = {
  id: 1,
  secid: 'SBER',
  isin: 'RU0009029540',
  name: 'Сбербанк',
  short_name: 'Сбербанк',
  type: 'STOCK',
  board: 'TQBR',
  currency: 'RUB',
  lot_size: 10,
  is_active: true,
};

const SBER_RESULT: AssetSearchItem = {
  secid: 'SBER',
  isin: 'RU0009029540',
  name: 'Сбербанк',
  short_name: 'Сбербанк',
  type: 'STOCK',
  board: 'TQBR',
  currency: 'RUB',
};

const GAZP_RESULT: AssetSearchItem = {
  secid: 'GAZP',
  isin: 'RU0007661625',
  name: 'Газпром',
  short_name: 'Газпром',
  type: 'STOCK',
  board: 'TQBR',
  currency: 'RUB',
};

const GAZP_ASSET: AssetDetail = {
  id: 3,
  secid: 'GAZP',
  isin: 'RU0007661625',
  name: 'Газпром',
  short_name: 'Газпром',
  type: 'STOCK',
  board: 'TQBR',
  currency: 'RUB',
  initial_face_value: null,
  current_face_value: null,
  lot_size: 10,
  is_active: true,
  amortizations: [],
};

describe('AssetSearchDialogComponent', () => {
  let assets: jasmine.SpyObj<AssetsService>;

  beforeEach(async () => {
    assets = jasmine.createSpyObj<AssetsService>('AssetsService', [
      'list',
      'search',
      'create',
      'get',
      'refresh',
      'remove',
    ]);
    assets.list.and.returnValue(of({ items: [LOCAL_ASSET] }));
    assets.search.and.returnValue(of({ items: [SBER_RESULT, GAZP_RESULT] }));
    assets.create.and.returnValue(of(GAZP_ASSET));

    await TestBed.configureTestingModule({
      imports: [AssetSearchDialogComponent],
      providers: [
        provideNoopAnimations(),
        providePrimeNG({ theme: { preset: Aura, options: { darkModeSelector: false } } }),
        { provide: AssetsService, useValue: assets },
      ],
    }).compileComponents();
  });

  function createOpened(): ComponentFixture<AssetSearchDialogComponent> {
    const fixture = TestBed.createComponent(AssetSearchDialogComponent);
    fixture.componentRef.setInput('visible', true);
    fixture.detectChanges();
    tick();
    return fixture;
  }

  it('loads the local assets when opened and debounces the search', fakeAsync(() => {
    const fixture = createOpened();
    const component = fixture.componentInstance;

    expect(assets.list).toHaveBeenCalledTimes(1);

    component.searchControl.setValue('SBER');
    tick(399);
    expect(assets.search).not.toHaveBeenCalled();

    tick(1);
    expect(assets.search).toHaveBeenCalledWith('SBER');
    expect(component.results().length).toBe(2);

    fixture.detectChanges();
  }));

  it('marks locally tracked securities as already added', fakeAsync(() => {
    const fixture = createOpened();
    const component = fixture.componentInstance;

    expect(component.isExisting(SBER_RESULT)).toBeTrue();
    expect(component.isExisting(GAZP_RESULT)).toBeFalse();

    fixture.detectChanges();
  }));

  it('compares the board as well as the secid', fakeAsync(() => {
    assets.list.and.returnValue(
      of({ items: [{ ...LOCAL_ASSET, id: 2, board: 'TQCB' }] }),
    );

    const fixture = createOpened();
    const component = fixture.componentInstance;

    expect(component.isExisting(SBER_RESULT)).toBeFalse();
    expect(component.isExisting({ ...SBER_RESULT, board: 'TQCB' })).toBeTrue();
  }));

  it('clears results and ignores a late response after reopening', fakeAsync(() => {
    const pending = new Subject<AssetSearchResponse>();
    assets.search.and.returnValue(pending.asObservable());

    const fixture = createOpened();
    const component = fixture.componentInstance;

    component.searchControl.setValue('SBER');
    tick(400);
    expect(component.loading()).toBeTrue();

    component.visible.set(false);
    fixture.detectChanges();
    component.visible.set(true);
    fixture.detectChanges();
    tick();

    expect(component.results()).toEqual([]);
    expect(component.loading()).toBeFalse();

    pending.next({ items: [SBER_RESULT] });
    pending.complete();
    tick();

    expect(component.results()).toEqual([]);
  }));

  it('adds a new security and emits the created asset', fakeAsync(() => {
    const fixture = createOpened();
    const component = fixture.componentInstance;
    const added: AssetDetail[] = [];
    component.added.subscribe((asset) => added.push(asset));

    component.add(GAZP_RESULT);

    expect(assets.create).toHaveBeenCalledWith({ secid: 'GAZP', board: 'TQBR' });
    expect(added).toEqual([GAZP_ASSET]);
    expect(component.visible()).toBeFalse();
  }));

  it('keeps the dialog open and marks the security after a duplicate error', fakeAsync(() => {
    assets.create.and.returnValue(
      throwError(
        () =>
          new ApiError(409, 'ASSET_ALREADY_EXISTS', 'Бумага GAZP на площадке TQBR уже добавлена', {
            secid: 'GAZP',
            board: 'TQBR',
          }),
      ),
    );

    const fixture = createOpened();
    const component = fixture.componentInstance;

    component.add(GAZP_RESULT);

    expect(component.visible()).toBeTrue();
    expect(component.error()?.code).toBe('ASSET_ALREADY_EXISTS');
    expect(component.isExisting(GAZP_RESULT)).toBeTrue();
    expect(component.addingSecid()).toBeNull();
  }));

  it('shows a MOEX search error and retries the last query', fakeAsync(() => {
    assets.search.and.returnValues(
      throwError(() => new ApiError(502, 'MOEX_UNAVAILABLE', 'MOEX недоступен')),
      of<AssetSearchResponse>({ items: [GAZP_RESULT] }),
    );

    const fixture = createOpened();
    const component = fixture.componentInstance;

    component.searchControl.setValue('GAZP');
    tick(400);
    fixture.detectChanges();

    expect(component.error()?.code).toBe('MOEX_UNAVAILABLE');
    expect(component.results()).toEqual([]);

    component.retry();
    tick();
    fixture.detectChanges();

    expect(assets.search).toHaveBeenCalledTimes(2);
    expect(component.error()).toBeNull();
    expect(component.results()).toEqual([GAZP_RESULT]);
  }));
});
