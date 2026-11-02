import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  HostListener,
  OnInit,
  ViewChild,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { ConfirmationService } from 'primeng/api';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { TagModule } from 'primeng/tag';
import { ToastModule } from 'primeng/toast';
import { filter } from 'rxjs';

import type { HealthResponse } from '../../core/api/models';
import { DatePipe } from '../../core/formatting/date.pipe';
import { HealthService } from '../../core/services/health.service';
import { rememberActiveElement, restoreFocus } from '../../shared/a11y/focus';
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
  private readonly confirmation = inject(ConfirmationService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly datePipe = inject(DatePipe);

  readonly navItems = NAV_ITEMS;
  readonly menuOpen = signal(false);

  @ViewChild('menuButton')
  private readonly menuButton?: ElementRef<HTMLButtonElement>;

  @ViewChild('mainContent')
  private readonly mainContent?: ElementRef<HTMLElement>;

  readonly health = signal<HealthResponse | null>(null);
  readonly healthState = signal<HealthState>('loading');
  readonly activeSection = signal<NavSection | null>(activeSectionForUrl(this.router.url));

  readonly version = computed(() => this.health()?.version ?? null);

  readonly healthPresentation = computed<HealthPresentation>(() => {
    switch (this.healthState()) {
      case 'ok':
        return { label: 'Сервер: работает', severity: 'success', icon: 'pi pi-check' };
      case 'degraded':
        return {
          label: 'Сервер: ограничен',
          severity: 'warn',
          icon: 'pi pi-exclamation-triangle',
        };
      case 'offline':
        return { label: 'Сервер: недоступен', severity: 'danger', icon: 'pi pi-times' };
      default:
        return {
          label: 'Сервер: проверка…',
          severity: 'secondary',
          icon: 'pi pi-spin pi-spinner',
        };
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

  private returnFocusAfterConfirm: HTMLElement | null = null;

  constructor() {
    this.router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe((event) => {
        this.activeSection.set(activeSectionForUrl(event.urlAfterRedirects));
      });

    this.confirmation.requireConfirmation$
      .pipe(
        filter((confirmation) => confirmation !== null),
        takeUntilDestroyed(),
      )
      .subscribe(() => {
        this.returnFocusAfterConfirm = rememberActiveElement();
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

  closeMenu(focusTarget: 'none' | 'menuButton' | 'main' = 'none'): void {
    this.menuOpen.set(false);

    if (focusTarget === 'menuButton') {
      this.menuButton?.nativeElement.focus();
    } else if (focusTarget === 'main') {
      this.mainContent?.nativeElement.focus();
    }
  }

  /** Skip the shell navigation without letting the base href change the route. */
  skipToMain(event: Event): void {
    event.preventDefault();
    this.mainContent?.nativeElement.focus();
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.menuOpen()) {
      this.closeMenu('menuButton');
    }
  }

  /** Return focus to the control that opened the confirmation dialog. */
  onConfirmHide(): void {
    restoreFocus(this.returnFocusAfterConfirm);
    this.returnFocusAfterConfirm = null;
  }
}
