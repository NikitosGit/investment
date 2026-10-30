import type { components } from './schema';

/**
 * Convenience aliases for the generated OpenAPI contract.
 *
 * `schema.ts` is produced by `npm run api:types` and must not be edited by
 * hand. Everything money-related arrives as a fixed-precision string; never
 * convert it to `number` for arithmetic, only for display.
 */
type Schemas = components['schemas'];

export type HealthResponse = Schemas['HealthResponse'];
export type PortfolioResponse = Schemas['PortfolioResponse'];
export type PortfolioUpdate = Schemas['PortfolioUpdate'];

export type AssetDetail = Schemas['AssetDetail'];
export type AssetListItem = Schemas['AssetListItem'];
export type AssetListResponse = Schemas['AssetListResponse'];
export type AssetSearchItem = Schemas['AssetSearchItem'];
export type AssetSearchResponse = Schemas['AssetSearchResponse'];
export type AssetCreateIn = Schemas['AssetCreateIn'];
export type AmortizationItem = Schemas['AmortizationItem'];

export type PositionItem = Schemas['PositionItem'];
export type PositionAsset = Schemas['PositionAsset'];
export type PositionListResponse = Schemas['PositionListResponse'];

export type DashboardResponse = Schemas['DashboardResponse'];
export type DashboardTotalsOut = Schemas['DashboardTotalsOut'];
export type DashboardSeriesPointOut = Schemas['DashboardSeriesPointOut'];

export type IncomeItem = Schemas['IncomeItem'];
export type IncomeListResponse = Schemas['IncomeListResponse'];
export type IncomeTotalsOut = Schemas['IncomeTotalsOut'];
export type IncomeCreateIn = Schemas['IncomeCreateIn'];
export type IncomeUpdateIn = Schemas['IncomeUpdateIn'];
export type MarkPaidIn = Schemas['MarkPaidIn'];

export type OperationResponse = Schemas['OperationResponse'];
export type OperationListResponse = Schemas['OperationListResponse'];
export type OperationCreateIn = Schemas['OperationCreateIn'];
export type OperationUpdateIn = Schemas['OperationUpdateIn'];

export type QuoteItem = Schemas['QuoteItem'];
export type QuoteHistoryResponse = Schemas['QuoteHistoryResponse'];
export type QuoteRefreshResponse = Schemas['QuoteRefreshResponse'];
export type QuoteRefreshErrorOut = Schemas['QuoteRefreshErrorOut'];
export type ManualQuoteIn = Schemas['ManualQuoteIn'];

export type SettingsResponse = Schemas['SettingsResponse'];
export type SettingsUpdate = Schemas['SettingsUpdate'];

export type SnapshotItem = Schemas['SnapshotItem'];
export type SnapshotListResponse = Schemas['SnapshotListResponse'];

export type BackupResponse = Schemas['BackupResponse'];

export type AssetType = Schemas['AssetType'];
export type PriceType = Schemas['PriceType'];
export type OperationType = Schemas['OperationType'];
export type IncomeKind = Schemas['IncomeKind'];
export type IncomeStatus = Schemas['IncomeStatus'];
export type DataSource = Schemas['DataSource'];

/** Dashboard-supported periods (derived from the settings contract). */
export type Period = SettingsResponse['dashboard_period'];

/** Quote-history-supported periods (wider than the dashboard). */
export type QuotePeriod = '1M' | '3M' | '6M' | '1Y' | '3Y' | '5Y' | 'ALL';

/** Where the current price came from. */
export type PriceSource = 'MOEX' | 'MANUAL' | 'COST';

/**
 * Error envelope returned by the backend.
 *
 * It is not part of OpenAPI, so the shape is declared on the client.
 */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

/** One entry of `details.errors` in a 422 `VALIDATION_ERROR` envelope. */
export interface ValidationFieldError {
  field: string;
  message: string;
  type: string;
}
