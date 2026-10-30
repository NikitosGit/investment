/**
 * Production/base environment.
 *
 * The application is served from the same origin as the API, so requests go
 * through the relative `/api` prefix. The development configuration replaces
 * this file with `environment.development.ts` (see `angular.json`).
 */
export const environment = {
  production: true,
  apiBaseUrl: '/api',
} as const;
