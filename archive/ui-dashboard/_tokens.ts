// Dashboard-scoped design tokens.
// Colors are CSS variables so they respond to data-theme synchronously (no flash).
// The `dark` param is kept for callers that need it for non-color logic.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function dashTokens(_dark?: boolean) {
  return {
    pageBg:       'var(--bg)',
    cardBg:       'var(--dash-card-bg)',
    cardBorder:   'var(--dash-card-border)',
    divider:      'var(--dash-divider)',
    radius:       8,
    sectionLabel: 'var(--dash-section)',
    dataMuted:    'var(--dash-muted)',
    dataBright:   'var(--fg1)',
    rowHover:     'var(--dash-row-hover)',
  } as const;
}

export const BRAND   = '#18E299';
export const BRAND_D = '#0fa76e';
export const VIOLET  = '#8B5CF6';
export const AMBER   = '#C37D0D';
export const RED     = '#D45656';
export const SANS    = 'var(--sans)';
export const MONO    = 'var(--mono)';
