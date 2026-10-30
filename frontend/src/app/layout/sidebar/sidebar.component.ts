import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import type { NavItem, NavSection } from '../navigation';

/** Desktop sidebar navigation. */
@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SidebarComponent {
  readonly items = input.required<readonly NavItem[]>();
  readonly active = input<NavSection | null>(null);

  isActive(item: NavItem): boolean {
    return this.active() === item.section;
  }
}
