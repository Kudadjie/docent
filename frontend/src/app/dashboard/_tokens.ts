// Dashboard-scoped design tokens — intentionally NOT promoted to globals.
// See HANDOFF.md: card bg is #111111 (vs #141414 elsewhere), radius 8px (vs 16px).
export function dashTokens(dark: boolean) {
  return {
    pageBg:       dark ? '#0d0d0d'                  : '#f8f9fa',
    cardBg:       dark ? '#111111'                  : '#ffffff',
    cardBorder:   dark ? 'rgba(255,255,255,0.08)'   : 'rgba(0,0,0,0.06)',
    divider:      dark ? 'rgba(255,255,255,0.06)'   : 'rgba(0,0,0,0.05)',
    radius:       8,
    sectionLabel: dark ? '#606060'                  : '#888888',
    dataMuted:    dark ? '#707070'                  : '#888888',
    dataBright:   dark ? '#ededed'                  : '#0d0d0d',
    rowHover:     dark ? 'rgba(255,255,255,0.025)'  : 'rgba(0,0,0,0.025)',
  } as const;
}

export const BRAND   = '#18E299';
export const BRAND_D = '#0fa76e';
export const VIOLET  = '#8B5CF6';
export const AMBER   = '#C37D0D';
export const RED     = '#D45656';
export const SANS    = 'var(--sans)';
export const MONO    = 'var(--mono)';
