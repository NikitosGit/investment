import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiClient } from '../api/api-client.service';
import type { AssetDetail, AssetListResponse, AssetSearchResponse } from '../api/models';
import { AssetsService } from './assets.service';

const ASSET: AssetDetail = {
  id: 1,
  secid: 'SBER',
  isin: 'RU0009029540',
  name: 'Сбербанк',
  short_name: 'Сбербанк',
  type: 'STOCK',
  board: 'TQBR',
  currency: 'RUB',
  initial_face_value: null,
  current_face_value: null,
  lot_size: 10,
  is_active: true,
  amortizations: [],
};

describe('AssetsService', () => {
  let service: AssetsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ApiClient],
    });

    service = TestBed.inject(AssetsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads the local asset list', () => {
    let result: AssetListResponse | undefined;
    service.list().subscribe((response) => (result = response));

    const request = http.expectOne('/api/assets');
    expect(request.request.method).toBe('GET');
    request.flush({ items: [] });

    expect(result?.items).toEqual([]);
  });

  it('searches MOEX with the trimmed query as a parameter', () => {
    let result: AssetSearchResponse | undefined;
    service.search('SBER').subscribe((response) => (result = response));

    const request = http.expectOne(
      (candidate) => candidate.url === '/api/assets/search' && candidate.params.get('q') === 'SBER',
    );
    expect(request.request.method).toBe('GET');
    request.flush({ items: [] });

    expect(result?.items).toEqual([]);
  });

  it('loads one asset by id', () => {
    let result: AssetDetail | undefined;
    service.get(1).subscribe((response) => (result = response));

    const request = http.expectOne('/api/assets/1');
    expect(request.request.method).toBe('GET');
    request.flush(ASSET);

    expect(result?.secid).toBe('SBER');
  });

  it('creates an asset from secid and board', () => {
    let result: AssetDetail | undefined;
    service.create({ secid: 'SBER', board: 'TQBR' }).subscribe((response) => (result = response));

    const request = http.expectOne('/api/assets');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ secid: 'SBER', board: 'TQBR' });
    request.flush(ASSET);

    expect(result?.id).toBe(1);
  });

  it('refreshes and removes an asset', () => {
    service.refresh(1).subscribe();
    const refresh = http.expectOne('/api/assets/1/refresh');
    expect(refresh.request.method).toBe('POST');
    refresh.flush(ASSET);

    service.remove(1).subscribe();
    const remove = http.expectOne('/api/assets/1');
    expect(remove.request.method).toBe('DELETE');
    remove.flush(null, { status: 204, statusText: 'No Content' });
  });
});
