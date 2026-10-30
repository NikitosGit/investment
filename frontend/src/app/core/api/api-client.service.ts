import { HttpClient, HttpParams, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { environment } from '../../../environments/environment';

/** Plain query-parameter record accepted by the client. */
export type QueryParams = Record<string, string | number | boolean | null | undefined>;

/** A downloaded file with the filename advertised by the server. */
export interface DownloadedFile {
  blob: Blob;
  filename: string;
}

/**
 * Thin typed wrapper around `HttpClient`.
 *
 * Responsibilities: base URL, query params, JSON typing and file downloads.
 * It deliberately contains no business rules and no calculations.
 */
@Injectable({ providedIn: 'root' })
export class ApiClient {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl.replace(/\/+$/, '');

  get<T>(path: string, params?: QueryParams): Observable<T> {
    return this.http.get<T>(this.url(path), { params: this.toParams(params) });
  }

  post<T, B = unknown>(path: string, body: B = {} as B): Observable<T> {
    return this.http.post<T>(this.url(path), body);
  }

  patch<T>(path: string, body: unknown): Observable<T> {
    return this.http.patch<T>(this.url(path), body);
  }

  delete(path: string): Observable<void> {
    return this.http.delete<void>(this.url(path));
  }

  /**
   * Download a binary response, extracting the filename from
   * `Content-Disposition` (falls back to `download`).
   */
  download(path: string, params?: QueryParams): Observable<DownloadedFile> {
    return this.http
      .get(this.url(path), {
        params: this.toParams(params),
        observe: 'response',
        responseType: 'blob',
      })
      .pipe(
        map((response: HttpResponse<Blob>) => ({
          blob: response.body ?? new Blob(),
          filename: extractFilename(response.headers.get('Content-Disposition')),
        })),
      );
  }

  private url(path: string): string {
    const suffix = path.startsWith('/') ? path : `/${path}`;
    return `${this.baseUrl}${suffix}`;
  }

  private toParams(params?: QueryParams): HttpParams {
    let result = new HttpParams();

    if (!params) {
      return result;
    }

    for (const [key, value] of Object.entries(params)) {
      if (value !== null && value !== undefined) {
        result = result.set(key, String(value));
      }
    }

    return result;
  }
}

/**
 * Extract a filename from a `Content-Disposition` header.
 *
 * Supports both RFC 5987 (`filename*=UTF-8''...`) and plain `filename="..."`.
 */
export function extractFilename(disposition: string | null): string {
  if (!disposition) {
    return 'download';
  }

  const encoded = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(disposition);
  if (encoded?.[1]) {
    try {
      return decodeURIComponent(encoded[1].trim());
    } catch {
      return encoded[1].trim();
    }
  }

  const plain = /filename\s*=\s*"?([^";]+)"?/i.exec(disposition);
  const candidate = plain?.[1]?.trim();
  return candidate && candidate.length > 0 ? candidate : 'download';
}
