import type { Status } from '@/lib/types';

const LIGHT: Record<Status, { bg: string; text: string; dot: string }> = {
  reading: { bg: '#FFF7ED', text: '#B45309', dot: '#F59E0B' },
  queued:  { bg: '#EFF6FF', text: '#1D4ED8', dot: '#3B82F6' },
  done:    { bg: '#d4fae8', text: '#0fa76e', dot: '#18E299' },
};

const DARK: Record<Status, { bg: string; text: string; dot: string }> = {
  reading: { bg: 'rgba(245,158,11,0.12)', text: '#F5A623', dot: '#F59E0B' },
  queued:  { bg: 'rgba(59,130,246,0.12)', text: '#60A5FA', dot: '#3B82F6' },
  done:    { bg: 'rgba(24,226,153,0.12)', text: '#18E299', dot: '#18E299' },
};

const LABEL: Record<Status, string> = {
  queued: 'Queued',
  reading: 'Reading',
  done: 'Done',
};

interface Props {
  status: Status;
  dark?: boolean;
}

export default function StatusBadge({ status, dark = false }: Props) {
  const cfg = (dark ? DARK : LIGHT)[status] ?? LIGHT.queued;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        background: cfg.bg,
        color: cfg.text,
        padding: '3px 10px',
        borderRadius: 9999,
        fontFamily: 'var(--mono)',
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.5px',
        textTransform: 'uppercase',
        whiteSpace: 'nowrap',
      }}
    >
      <span
        style={{
          width: 5,
          height: 5,
          borderRadius: '50%',
          background: cfg.dot,
          flexShrink: 0,
        }}
      />
      {LABEL[status]}
    </span>
  );
}
