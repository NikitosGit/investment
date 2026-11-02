import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiClient } from '../api/api-client.service';
import type { DownloadedFile } from '../api/api-client.service';
import type { BackupResponse } from '../api/models';

/** Supported export formats: JSON, or a ZIP archive with three CSV files. */
export type ExportFormat = 'json' | 'csv';

/** Typed access to system-level operations: backup and data export. */
@Injectable({ providedIn: 'root' })
export class SystemService {
  private readonly api = inject(ApiClient);

  /** Create a SQLite backup on the server. The file is not served over HTTP. */
  createBackup(): Observable<BackupResponse> {
    return this.api.post<BackupResponse>('/backup');
  }

  /** Download a JSON export or a ZIP of CSV files, including the server filename. */
  export(format: ExportFormat): Observable<DownloadedFile> {
    return this.api.download('/export', { format });
  }
}
