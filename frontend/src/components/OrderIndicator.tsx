'use client';

interface Props {
  order: number;
}

function orderLevel(order: number): 'high' | 'medium' | 'low' | 'unordered' {
  if (order === 0) return 'unordered';
  if (order <= 3) return 'high';
  if (order <= 7) return 'medium';
  return 'low';
}

const LEVEL_COLOR = {
  high:      '#D45656',
  medium:    '#C37D0D',
  low:       '#18E299',
  unordered: '#888888',
};

export default function OrderIndicator({ order }: Props) {
  const level = orderLevel(order);
  const color = LEVEL_COLOR[level];
  const label = order === 0 ? '-' : `#${order}`;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: color,
          flexShrink: 0,
          animation: level === 'high' ? 'pulse-high 2s ease infinite' : 'none',
        }}
      />
      <span
        style={{
          fontFamily: 'var(--sans)',
          fontSize: 13,
          color: 'var(--fg3)',
          fontWeight: 500,
        }}
      >
        {label}
      </span>
    </div>
  );
}
