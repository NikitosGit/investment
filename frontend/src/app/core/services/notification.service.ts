import { Injectable, inject } from '@angular/core';
import { MessageService } from 'primeng/api';

import { ApiError } from '../api/api-error';

type Severity = 'success' | 'info' | 'warn' | 'error';

interface LastMessage {
  signature: string;
  at: number;
}

/** Default lifetime per severity in milliseconds. */
const LIFETIME: Record<Severity, number> = {
  success: 4000,
  info: 4500,
  warn: 6000,
  error: 7000,
};

/** Ignore an identical toast repeated within this window. */
const DEDUPE_WINDOW_MS = 3000;

/**
 * Centralized user notifications on top of PrimeNG `MessageService`.
 *
 * Toast messages are for user actions only (not every HTTP request). Identical
 * messages fired in quick succession are collapsed into one.
 */
@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly messages = inject(MessageService);
  private last?: LastMessage;

  success(detail: string, summary = 'Готово'): void {
    this.show('success', summary, detail);
  }

  info(detail: string, summary = 'Информация'): void {
    this.show('info', summary, detail);
  }

  warn(detail: string, summary = 'Внимание'): void {
    this.show('warn', summary, detail);
  }

  error(error: unknown, summary = 'Ошибка'): void {
    this.show('error', summary, messageOf(error));
  }

  private show(severity: Severity, summary: string, detail?: string): void {
    const signature = `${severity}|${summary}|${detail ?? ''}`;
    const now = Date.now();

    if (this.last && this.last.signature === signature && now - this.last.at < DEDUPE_WINDOW_MS) {
      return;
    }

    this.last = { signature, at: now };
    this.messages.add({
      severity,
      summary,
      detail,
      life: LIFETIME[severity],
      closable: true,
    });
  }
}

function messageOf(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }

  return 'Не удалось выполнить действие. Попробуйте ещё раз';
}
