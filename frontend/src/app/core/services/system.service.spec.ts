import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiClient } from '../api/api-client.service';
import type { BackupResponse } from '../api/models';
import { SystemService } from './system.service';

const BACKUP: BackupResponse = {
  path: 'data/backups/investments-20261030-181012.db',
  size_bytes: 106496,
  created_at: '2026-10-30T18:10:12.870080+03:00',
};

describe('SystemService', () => {
  let service: SystemService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ApiClient],
    });

    service = TestBed.inject(SystemService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('creates a backup with POST /api/backup', () => {
    let result: BackupResponse | undefined;
    service.createBackup().subscribe((response) => (result = response));

    const request = http.expectOne('/api/backup');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({});
    request.flush(BACKUP);

    expect(result).toEqual(BACKUP);
  });

  it('exports JSON with the format query parameter and passes the blob through', () => {
    let blob: Blob | undefined;
    let filename = '';

    service.export('json').subscribe((file) => {
      blob = file.blob;
      filename = file.filename;
    });

    const request = http.expectOne(
      (candidate) =>
        candidate.url === '/api/export' && candidate.params.get('format') === 'json',
    );
    expect(request.request.method).toBe('GET');

    const fileBlob = new Blob(['{"ok":true}'], { type: 'application/json' });
    request.flush(fileBlob, {
      headers: {
        'Content-Disposition':
          'attachment; filename="investments-export-20261030-181012.json"',
      },
    });

    expect(filename).toBe('investments-export-20261030-181012.json');
    expect(blob).toBe(fileBlob);
  });

  it('exports CSV as a ZIP archive', () => {
    let filename = '';

    service.export('csv').subscribe((file) => (filename = file.filename));

    const request = http.expectOne(
      (candidate) =>
        candidate.url === '/api/export' && candidate.params.get('format') === 'csv',
    );
    request.flush(new Blob(['zip'], { type: 'application/zip' }), {
      headers: {
        'Content-Disposition':
          'attachment; filename="investments-export-20261030-181012.zip"',
      },
    });

    expect(filename).toBe('investments-export-20261030-181012.zip');
  });

  it('keeps the API-client fallback filename when Content-Disposition is missing', () => {
    let filename = '';

    service.export('json').subscribe((file) => (filename = file.filename));

    http.expectOne('/api/export?format=json').flush(new Blob(['{}']));

    expect(filename).toBe('download');
  });
});
