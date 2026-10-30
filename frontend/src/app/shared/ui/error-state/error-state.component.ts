import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { ButtonModule } from 'primeng/button';

/** Inline load-failure block with a retry action. */
@Component({
  selector: 'app-error-state',
  standalone: true,
  imports: [ButtonModule],
  templateUrl: './error-state.component.html',
  styleUrl: './error-state.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ErrorStateComponent {
  readonly title = input<string>('Не удалось загрузить данные');
  readonly message = input.required<string>();
  readonly retry = output<void>();
}
