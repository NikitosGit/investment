import { ChangeDetectionStrategy, Component } from '@angular/core';

import { EmptyStateComponent } from '../../shared/ui/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/ui/page-header/page-header.component';

@Component({
  selector: 'app-income-page',
  standalone: true,
  imports: [PageHeaderComponent, EmptyStateComponent],
  templateUrl: './income-page.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class IncomePage {}
