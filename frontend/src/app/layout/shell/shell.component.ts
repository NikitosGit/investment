import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  HostListener,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { TagModule } from 'primeng/tag';
import { ToastModule } from 'primeng/toast';
import { filter } from 'rxjs';

import type { HealthResponse } from '../../core/api/models';
import { DatePipe } from '../../core/formatting/date.pipe';
import { HealthService } from '../../core/services/health.service';
import { NAV_ITEMS, activeSectionForUrl } from '../navigation';
import type { NavSection } from '../navigation';
import { SidebarComponent } from '../sidebar/sidebar.component';

type HealthState = 'loading' | 'ok' | 'degraded' | 'offline';
type BadgeSeverity = 'success' | 'secondary' | 'info' | 'warn' | 'danger' | 'contrast';

interface HealthPresentation {
  label: string;
  severity: BadgeSeverity;
  icon: string;
}

const DESKTOP_QUERY = '(min-width: 901px)';

/** Application shell: topbar, desktop sidebar, mobile navigation, notifications. */
@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [
    RouterLink,
    RouterOutlet,
    SidebarComponent,
    ToastModule,
    ConfirmDialogModule,
    TagModule,
  ],
  providers: [DatePipe],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ShellComponent implements OnInit {
  private readonly healthService = inject(HealthService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private readonly datePipe = inject(DatePipe);

  readonly navItems = NAV_ITEMS;
  readonly menuOpen = signal(false);
  readonly health = signal<HealthResponse | null>(null);
  readonly healthState = signal<HealthState>('loading');
  readonly activeSection = signal<NavSection | null>(activeSectionForUrl(this.router.url));

  readonly version = computed(() => this.health()?.version ?? null);

  readonly healthPresentation = computed<HealthPresentation>(() => {
    switch (this.healthState()) {
      case 'ok':
        return { label: 'API: ok', severity: 'success', icon: 'pi pi-check' };
      case 'degraded':
        return { label: 'API: degraded', severity: 'warn', icon: 'pi pi-exclamation-triangle' };
      case 'offline':
        return { label: 'API: offline', severity: 'danger', icon: 'pi pi-times' };
      default:
        return { label: 'API: проверка…', severity: 'secondary', icon: 'pi pi-spin pi-spinner' };
    }
  });

  readonly healthTooltip = computed(() => {
    const health = this.health();
    if (!health?.last_quote_refresh_at) {
      return '';
    }

    return `Последнее обновление котировок: ${this.datePipe.transform(health.last_quote_refresh_at)}`;
  });

  private readonly onViewportChange = (event: MediaQueryListEvent): void => {
    if (event.matches) {
      this.closeMenu();
    }
  };

  constructor() {
    this.router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe((event) => {
        this.activeSection.set(activeSectionForUrl(event.urlAfterRedirects));
      });
  }

  ngOnInit(): void {
    this.healthService.get().subscribe({
      next: (health) => {
        this.health.set(health);
        this.healthState.set(health.status === 'ok' ? 'ok' : 'degraded');
      },
      error: () => {
        // The shell must stay usable even when the API is unreachable.
        this.healthState.set('offline');
      },
    });

    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
      const query = window.matchMedia(DESKTOP_QUERY);
      query.addEventListener('change', this.onViewportChange);
      this.destroyRef.onDestroy(() => query.removeEventListener('change', this.onViewportChange));
    }
  }

  isActive(section: NavSection): boolean {
    return this.activeSection() === section;
  }

  toggleMenu(): void {
    if (this.menuOpen()) {
      this.closeMenu();
    } else {
      this.menuOpen.set(true);
    }
  }

  closeMenu(): void {
    this.menuOpen.set(false);
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.closeMenu();
  }
}
