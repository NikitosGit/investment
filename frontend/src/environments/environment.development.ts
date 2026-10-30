/**
 * Development environment.
 *
 * `ng serve` proxies `/api` to `http://127.0.0.1:8000` (see
 * `proxy.conf.json`), therefore the browser only ever talks to the dev server
 * origin. No CORS configuration is required for local development.
 */
export const environment = {
  production: false,
  apiBaseUrl: '/api',
} as const;
