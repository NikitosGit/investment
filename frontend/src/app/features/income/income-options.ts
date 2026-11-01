import type { AssetListItem } from '../../core/api/models';
import type { SelectOption } from '../../shared/ui/select-option';

/** Build the asset choices shared by the income filter and the income dialog. */
export function toIncomeAssetOptions(
  assets: readonly AssetListItem[],
): SelectOption<number>[] {
  return assets.map((asset) => ({
    value: asset.id,
    label: `${asset.secid} · ${asset.short_name ?? asset.name}`,
  }));
}
