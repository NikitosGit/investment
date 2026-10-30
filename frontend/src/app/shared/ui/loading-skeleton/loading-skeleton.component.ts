import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { SkeletonModule } from 'primeng/skeleton';

/** Skeleton placeholder for rows or cards while data is loading. */
@Component({
  selector: 'app-loading-skeleton',
  standalone: true,
  imports: [SkeletonModule],
  templateUrl: './loading-skeleton.component.html',
  styleUrl: './loading-skeleton.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoadingSkeletonComponent {
  readonly rows = input<number>(3);
  readonly cards = input<number>(0);

  readonly rowItems = computed(() => Array.from({ length: Math.max(0, this.rows()) }));
  readonly cardItems = computed(() => Array.from({ length: Math.max(0, this.cards()) }));
}
