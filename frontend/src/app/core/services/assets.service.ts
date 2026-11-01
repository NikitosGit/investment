import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiClient } from '../api/api-client.service';
import type {
  AssetCreateIn,
  AssetDetail,
  AssetListResponse,
  AssetSearchResponse,
} from '../api/models';

/** Typed access to tracked assets and MOEX search. */
@Injectable({ providedIn: 'root' })
export class AssetsService {
  private readonly api = inject(ApiClient);

  list(): Observable<AssetListResponse> {
    return this.api.get<AssetListResponse>('/assets');
  }

  search(query: string): Observable<AssetSearchResponse> {
    return this.api.get<AssetSearchResponse>('/assets/search', { q: query });
  }

  get(assetId: number): Observable<AssetDetail> {
    return this.api.get<AssetDetail>(`/assets/${assetId}`);
  }

  create(payload: AssetCreateIn): Observable<AssetDetail> {
    return this.api.post<AssetDetail, AssetCreateIn>('/assets', payload);
  }

  refresh(assetId: number): Observable<AssetDetail> {
    return this.api.post<AssetDetail>(`/assets/${assetId}/refresh`);
  }

  remove(assetId: number): Observable<void> {
    return this.api.delete(`/assets/${assetId}`);
  }
}
