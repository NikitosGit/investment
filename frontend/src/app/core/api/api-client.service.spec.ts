import { HttpHeaders, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiClient, extractFilename } from './api-client.service';

describe('ApiClient', () => {
  let client: ApiClient;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ApiClient],
    });

    client = TestBed.inject(ApiClient);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('prefixes /api and skips null/undefined query params', () => {
    client
      .get<{ ok: boolean }>('/health', { period: '1Y', empty: null, missing: undefined })
      .subscribe();

    const request = http.expectOne((req) => req.url === '/api/health');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('period')).toBe('1Y');
    expect(request.request.params.has('empty')).toBeFalse();
    expect(request.request.params.has('missing')).toBeFalse();
    request.flush({ ok: true });
  });

  it('keeps false and 0 query params', () => {
    client
      .get<{ ok: boolean }>('/health', { flag: false, count: 0, zeroString: '0' })
      .subscribe();

    const request = http.expectOne((req) => req.url === '/api/health');
    expect(request.request.params.get('flag')).toBe('false');
    expect(request.request.params.get('count')).toBe('0');
    expect(request.request.params.get('zeroString')).toBe('0');
    request.flush({ ok: true });
  });

  it('supports post, patch and delete verbs', () => {
    client.post('/operations', { quantity: 1 }).subscribe();
    client.patch('/settings', { dashboard_period: '3M' }).subscribe();
    client.delete('/operations/1').subscribe();

    http.expectOne('/api/operations').flush({});
    http.expectOne('/api/settings').flush({});
    const remove = http.expectOne('/api/operations/1');
    expect(remove.request.method).toBe('DELETE');
    remove.flush(null);
  });

  it('sends an empty object for a body-less POST', () => {
    client.post('/income/3/mark-paid').subscribe();

    const request = http.expectOne('/api/income/3/mark-paid');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({});
    request.flush({});
  });

  it('downloads a blob and reads the filename from Content-Disposition', () => {
    let filename = '';

    client.download('/export', { format: 'csv' }).subscribe((file) => {
      filename = file.filename;
    });

    const request = http.expectOne(
      (req) => req.url === '/api/export' && req.params.get('format') === 'csv',
    );
    request.flush(new Blob(['data']), {
      headers: new HttpHeaders({
        'Content-Disposition': 'attachment; filename="investments-export-20261030.zip"',
      }),
    });

    expect(filename).toBe('investments-export-20261030.zip');
  });
});

describe('extractFilename', () => {
  it('reads a plain filename', () => {
    expect(extractFilename('attachment; filename="report.json"')).toBe('report.json');
  });

  it('reads an RFC 5987 filename', () => {
    expect(extractFilename("attachment; filename*=UTF-8''%D0%BE%D1%82%D1%87%D0%B5%D1%82.json")).toBe(
      'отчет.json',
    );
  });

  it('falls back when the header is missing', () => {
    expect(extractFilename(null)).toBe('download');
  });
});
