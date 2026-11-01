import type {
  AssetType,
  DataSource,
  IncomeKind,
  IncomeStatus,
  OperationType,
} from '../api/models';

const ASSET_TYPE_LABELS: Record<AssetType, string> = {
  STOCK: 'Акция',
  BOND: 'Облигация',
};

const OPERATION_TYPE_LABELS: Record<OperationType, string> = {
  BUY: 'Покупка',
  SELL: 'Продажа',
};

const INCOME_KIND_LABELS: Record<IncomeKind, string> = {
  DIVIDEND: 'Дивиденд',
  COUPON: 'Купон',
};

const INCOME_STATUS_LABELS: Record<IncomeStatus, string> = {
  PAID: 'Выплачено',
  EXPECTED: 'Ожидается',
};

const DATA_SOURCE_LABELS: Record<DataSource, string> = {
  MOEX: 'MOEX',
  MANUAL: 'Вручную',
};

/** Human-readable asset type ("Акция" / "Облигация"). */
export function assetTypeLabel(value: AssetType): string {
  return ASSET_TYPE_LABELS[value];
}

/** Human-readable operation type ("Покупка" / "Продажа"). */
export function operationTypeLabel(value: OperationType): string {
  return OPERATION_TYPE_LABELS[value];
}

/** Human-readable income kind ("Дивиденд" / "Купон"). */
export function incomeKindLabel(value: IncomeKind): string {
  return INCOME_KIND_LABELS[value];
}

/** Human-readable income status ("Выплачено" / "Ожидается"). */
export function incomeStatusLabel(value: IncomeStatus): string {
  return INCOME_STATUS_LABELS[value];
}

/** Human-readable data source ("MOEX" / "Вручную"). */
export function dataSourceLabel(value: DataSource): string {
  return DATA_SOURCE_LABELS[value];
}
