import { HttpErrorResponse } from '@angular/common/http';

import type { ApiErrorBody, ValidationFieldError } from './models';

/** Default user-facing messages (never expose raw payloads or stack traces). */
const NETWORK_MESSAGE = 'Нет связи с backend';
const UNKNOWN_MESSAGE = 'Произошла непредвиденная ошибка';
const SERVER_MESSAGE = 'Ошибка сервера. Попробуйте повторить позже';
const NOT_FOUND_MESSAGE = 'Запрашиваемые данные не найдены';
const VALIDATION_MESSAGE = 'Ошибка валидации данных';

/**
 * Normalized application error.
 *
 * Carries the backend error `code` so callers can react to specific business
 * cases (`INSUFFICIENT_QUANTITY`, `ASSET_IN_USE`, ...). The original transport
 * error is kept as `cause` for logging only.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
    cause?: unknown,
  ) {
    super(message, { cause });
    this.name = 'ApiError';
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (!isRecord(value) || !isRecord(value['error'])) {
    return false;
  }
  const body = value['error'];
  return typeof body['code'] === 'string' && typeof body['message'] === 'string';
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

function fallbackMessage(status: number): string {
  if (status === 0) {
    return NETWORK_MESSAGE;
  }
  if (status === 404) {
    return NOT_FOUND_MESSAGE;
  }
  if (status === 422) {
    return VALIDATION_MESSAGE;
  }
  if (status >= 500) {
    return SERVER_MESSAGE;
  }
  return UNKNOWN_MESSAGE;
}

/**
 * Build an `ApiError` from an HTTP status and an already-decoded body.
 *
 * `rawBody` may be a parsed JSON object or the raw response text.
 */
export function apiErrorFromBody(
  status: number,
  rawBody: unknown,
  transport?: unknown,
): ApiError {
  let body = rawBody;

  if (typeof rawBody === 'string') {
    body = parseJson(rawBody);
  }

  if (isApiErrorBody(body)) {
    const details = isRecord(body.error.details) ? body.error.details : {};
    return new ApiError(status, body.error.code, body.error.message, details, transport);
  }

  return new ApiError(status, 'UNKNOWN_ERROR', fallbackMessage(status), {}, transport);
}

/**
 * Map any thrown value to an `ApiError`.
 *
 * * network failure (`status === 0`) -> `NETWORK_ERROR`
 * * backend envelope -> code/message/details from the envelope
 * * anything else -> `UNKNOWN_ERROR` with a generic message
 */
export function mapHttpError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }

  if (error instanceof HttpErrorResponse) {
    if (error.status === 0) {
      return new ApiError(0, 'NETWORK_ERROR', NETWORK_MESSAGE, {}, error);
    }

    const body = error.error;

    if (body instanceof Blob) {
      // Blob bodies are handled asynchronously by `mapHttpErrorAsync`.
      return new ApiError(
        error.status,
        'UNKNOWN_ERROR',
        fallbackMessage(error.status),
        {},
        error,
      );
    }

    return apiErrorFromBody(error.status, body, error);
  }

  if (error instanceof Error) {
    return new ApiError(0, 'UNKNOWN_ERROR', UNKNOWN_MESSAGE, {}, error);
  }

  return new ApiError(0, 'UNKNOWN_ERROR', UNKNOWN_MESSAGE, {}, error);
}

/**
 * Read the structured field errors of a `422 VALIDATION_ERROR`.
 *
 * The backend stores them in `details.errors`; unknown shapes are ignored so a
 * form can still show the general message from `ApiError.message`.
 */
export function validationErrors(error: ApiError): ValidationFieldError[] {
  const raw = error.details['errors'];
  if (!Array.isArray(raw)) {
    return [];
  }

  return raw.flatMap((item) => {
    if (!isRecord(item) || typeof item['field'] !== 'string' || typeof item['message'] !== 'string') {
      return [];
    }

    return [
      {
        field: item['field'],
        message: item['message'],
        type: typeof item['type'] === 'string' ? item['type'] : 'value_error',
      },
    ];
  });
}

/** Strip the `body.`/`query.`/`path.` prefix from a backend field path. */
export function formFieldName(field: string): string {
  return field.replace(/^(?:body|query|path)\./, '');
}

/**
 * Async variant that reads `Blob` error bodies (file downloads).
 */
export async function mapHttpErrorAsync(error: unknown): Promise<ApiError> {
  if (error instanceof HttpErrorResponse && error.error instanceof Blob) {
    try {
      const text = await error.error.text();
      return apiErrorFromBody(error.status, text, error);
    } catch {
      return new ApiError(error.status, 'UNKNOWN_ERROR', fallbackMessage(error.status), {}, error);
    }
  }

  return mapHttpError(error);
}
