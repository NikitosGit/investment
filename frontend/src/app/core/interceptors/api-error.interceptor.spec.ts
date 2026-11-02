import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiClient } from '../api/api-client.service';
import { ApiError } from '../api/api-error';
import { apiErrorInterceptor } from './api-error.interceptor';

const ENVELOPE = {
  error: {
    code: 'ASSET_IN_USE',
    message: 'Нельзя удалить актив',
    details: { asset_id: 1 },
  },
};

describe('apiErrorInterceptor', () => {
  let client: ApiClient;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiErrorInterceptor])),
        provideHttpClientTesting(),
        ApiClient,
      ],
    });

    client = TestBed.inject(ApiClient);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('normalizes a backend error envelope', () => {
    let caught: ApiError | undefined;
    client.get('/assets/1').subscribe({ error: (error: ApiError) => (caught = error) });

    http
      .expectOne('/api/assets/1')
      .flush(ENVELOPE, { status: 409, statusText: 'Conflict' });

    expect(caught).toBeInstanceOf(ApiError);
    expect(caught?.status).toBe(409);
    expect(caught?.code).toBe('ASSET_IN_USE');
    expect(caught?.details['asset_id']).toBe(1);
  });

  it('normalizes a network failure', () => {
    let caught: ApiError | undefined;
    client.get('/health').subscribe({ error: (error: ApiError) => (caught = error) });

    http.expectOne('/api/health').error(new ProgressEvent('error'));

    expect(caught?.status).toBe(0);
    expect(caught?.code).toBe('NETWORK_ERROR');
    expect(caught?.message).toBe('Нет связи с сервером');
  });

  it('normalizes an unknown non-JSON failure', () => {
    let caught: ApiError | undefined;
    client.get('/health').subscribe({ error: (error: ApiError) => (caught = error) });

    http
      .expectOne('/api/health')
      .flush('<html>internal failure</html>', { status: 500, statusText: 'Server Error' });

    expect(caught?.code).toBe('UNKNOWN_ERROR');
    expect(caught?.message).not.toContain('internal failure');
  });

  it('reads a Blob error body from a file download', async () => {
    const caught = new Promise<ApiError>((resolve, reject) => {
      client.download('/export', { format: 'csv' }).subscribe({
        next: () => reject(new Error('expected the download to fail')),
        error: (error: ApiError) => resolve(error),
      });
    });

    http
      .expectOne((request) => request.url === '/api/export')
      .flush(new Blob([JSON.stringify(ENVELOPE)], { type: 'application/json' }), {
        status: 409,
        statusText: 'Conflict',
      });

    const error = await caught;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe('ASSET_IN_USE');
  });
});
