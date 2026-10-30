import { activeSectionForUrl } from './navigation';

describe('activeSectionForUrl', () => {
  it('maps top-level routes to their section', () => {
    expect(activeSectionForUrl('/dashboard')).toBe('dashboard');
    expect(activeSectionForUrl('/portfolio')).toBe('portfolio');
    expect(activeSectionForUrl('/income')).toBe('income');
    expect(activeSectionForUrl('/settings')).toBe('settings');
  });

  it('ignores query strings and fragments', () => {
    expect(activeSectionForUrl('/dashboard?period=1Y')).toBe('dashboard');
    expect(activeSectionForUrl('/portfolio#positions')).toBe('portfolio');
    expect(activeSectionForUrl('/income?status=PAID#totals')).toBe('income');
  });

  it('treats asset cards as part of the portfolio', () => {
    expect(activeSectionForUrl('/assets')).toBe('portfolio');
    expect(activeSectionForUrl('/assets/')).toBe('portfolio');
    expect(activeSectionForUrl('/assets/1')).toBe('portfolio');
    expect(activeSectionForUrl('/assets/1?tab=operations#history')).toBe('portfolio');
  });

  it('accepts trailing slashes', () => {
    expect(activeSectionForUrl('/dashboard/')).toBe('dashboard');
    expect(activeSectionForUrl('/portfolio/')).toBe('portfolio');
    expect(activeSectionForUrl('/income/')).toBe('income');
    expect(activeSectionForUrl('/settings/')).toBe('settings');
  });

  it('does not match partial prefixes', () => {
    expect(activeSectionForUrl('/dashboardish')).toBeNull();
    expect(activeSectionForUrl('/portfoliox')).toBeNull();
    expect(activeSectionForUrl('/assetsish')).toBeNull();
  });

  it('returns null for root and unknown routes', () => {
    expect(activeSectionForUrl('/')).toBeNull();
    expect(activeSectionForUrl('')).toBeNull();
    expect(activeSectionForUrl('/unknown')).toBeNull();
    expect(activeSectionForUrl('/not-found?x=1')).toBeNull();
  });
});
