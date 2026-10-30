import { HttpErrorResponse } from '@angular/common/http';

import {
  ApiError,
  apiErrorFromBody,
  mapHttpError,
  mapHttpErrorAsync,
} from './api-error';

const ENVELOPE = {
  error: {
    code: 'INSUFFICIENT_QUANTITY',
    message: 'Нельзя продать 20: доступно 15',
    details: { asset_id: 1, available: 15, requested: 20 },
  },
};

describe('ApiError mapping', () => {
  it('maps a backend error envelope', () => {
    const error = apiErrorFromBody(409, ENVELOPE);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(409);
    expect(error.code).toBe('INSUFFICIENT_QUANTITY');
    expect(error.message).toBe('Нельзя продать 20: доступно 15');
    expect(error.details['available']).toBe(15);
  });

  it('maps a raw JSON envelope string', () => {
    const error = apiErrorFromBody(400, JSON.stringify(ENVELOPE));

    expect(error.code).toBe('INSUFFICIENT_QUANTITY');
  });

  it('maps an HttpErrorResponse carrying an envelope', () => {
    const response = new HttpErrorResponse({ status: 404, error: ENVELOPE });
    const error = mapHttpError(response);

    expect(error.status).toBe(404);
    expect(error.code).toBe('INSUFFICIENT_QUANTITY');
  });

  it('maps a network failure (status 0)', () => {
    const response = new HttpErrorResponse({ status: 0, error: new ProgressEvent('error') });
    const error = mapHttpError(response);

    expect(error.status).toBe(0);
    expect(error.code).toBe('NETWORK_ERROR');
    expect(error.message).toBe('Нет связи с backend');
  });

  it('maps an unknown non-JSON body to a generic error', () => {
    const response = new HttpErrorResponse({ status: 500, error: '<html>stack trace</html>' });
    const error = mapHttpError(response);

    expect(error.code).toBe('UNKNOWN_ERROR');
    expect(error.message).not.toContain('stack trace');
    expect(error.message.length).toBeGreaterThan(0);
  });

  it('maps arbitrary thrown values without leaking internals', () => {
    const error = mapHttpError(new Error('boom'));

    expect(error.code).toBe('UNKNOWN_ERROR');
    expect(error.message).not.toContain('boom');
  });

  it('passes an existing ApiError through unchanged', () => {
    const original = new ApiError(409, 'ASSET_IN_USE', 'Нельзя удалить актив');
    expect(mapHttpError(original)).toBe(original);
  });

  it('reads a Blob error body asynchronously', async () => {
    const response = new HttpErrorResponse({
      status: 400,
      error: new Blob([JSON.stringify(ENVELOPE)], { type: 'application/json' }),
    });

    const error = await mapHttpErrorAsync(response);

    expect(error.code).toBe('INSUFFICIENT_QUANTITY');
    expect(error.details['requested']).toBe(20);
  });
});
