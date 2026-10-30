import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, from, mergeMap, throwError } from 'rxjs';

import { mapHttpError, mapHttpErrorAsync } from '../api/api-error';

/**
 * Converts every transport failure into a normalized `ApiError`.
 *
 * Components and services never see `HttpErrorResponse`; they receive an
 * `ApiError` carrying `status`, `code`, `message` and `details`.
 */
export const apiErrorInterceptor: HttpInterceptorFn = (request, next) =>
  next(request).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.error instanceof Blob) {
        return from(mapHttpErrorAsync(error)).pipe(
          mergeMap((apiError) => throwError(() => apiError)),
        );
      }

      return throwError(() => mapHttpError(error));
    }),
  );
