import type { Status } from '@/lib/types';

const LIGHT: Record<Status, { bg: string; text: string; dot: string }> = {
  reading: { bg: '#fbeede', text: '#b45309', dot: '#e8a55a' },
  queued:  { bg: '#e6f2ee', text: '#2f7d6e', dot: '#5db8a6' },
  done:    { bg: '#e4f1e6', text: '#3f8f54', dot: '#5db872' },
  removed: { bg: '#efe9de', text: '#8e8b82', dot: '#c8c1b4' },
};

const DARK: Record<Status, { bg: string; text: string; dot: string }> = {
  reading: { bg: 'rgba(232,165,90,0.14)', text: '#e8a55a', dot: '#e8a55a' },
  queued:  { bg: 'rgba(93,184,166,0.14)', text: '#7fcabb', dot: '#5db8a6' },
  done:    { bg: 'rgba(93,184,114,0.14)', text: '#7fcb8f', dot: '#5db872' },
  removed: { bg: 'rgba(160,157,150,0.12)', text: '#a09d96', dot: '#6f6c64' },
};

const LABEL: Record<Status, string> = {
  queued: 'Queued',
  reading: 'Reading',
  done: 'Done',
  removed: 'Removed',
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
