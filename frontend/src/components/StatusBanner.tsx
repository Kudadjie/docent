'use client';

import { Sun, Moon, Bell, RefreshCw, Info, AlertTriangle, XCircle, X } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import type { BannerCounts } from '@/lib/types';
import { useNotifications, type AppNotification } from '@/lib/notifications';

export type DotState = 'idle' | 'working' | 'error' | 'done';

const DOT_COLOR: Record<DotState, string> = {
  idle:    '#18E299',
  working: '#F5A623',
  error:   '#E53535',
  done:    '#18E299',
};

const DOT_ANIM: Record<DotState, string> = {
  idle:    'none',
  working: 'logo-dot-blink 1s step-end infinite',
  error:   'logo-dot-blink 0.7s step-end infinite',
  done:    'logo-dot-done 0.5s ease-in-out 3',
};

interface Props {
  dark: boolean;
  onToggleDark: () => void;
  dotState?: DotState;
  // Reading-page extras — all optional; omit on non-reading pages
  banner?: BannerCounts;
  lastUpdated?: string | null;
  databaseCount?: number | null;
}

function formatAge(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  } catch {
    return '—';
  }
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500,
        color: 'var(--fg4)', letterSpacing: '0.7px', textTransform: 'uppercase',
      }}>
        {label}
      </span>
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600,
        color: 'var(--fg1)', letterSpacing: '0.4px',
      }}>
        {value}
      </span>
    </div>
  );
}

const NOTIF_ICON: Record<AppNotification['type'], React.ReactNode> = {
  update:  <RefreshCw size={12} strokeWidth={2} color="#0fa76e" />,
  info:    <Info size={12} strokeWidth={2} color="#3B82F6" />,
  warning: <AlertTriangle size={12} strokeWidth={2} color="#F5A623" />,
  error:   <XCircle size={12} strokeWidth={2} color="#E53535" />,
};

function NotificationDropdown({
  notifications,
  onDismiss,
  onMarkAllRead,
  onClearAll,
  onClose,
}: {
  notifications: AppNotification[];
  onDismiss: (id: string) => void;
  onMarkAllRead: () => void;
  onClearAll: () => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [onClose]);

  return (
    <div
      ref={ref}
      style={{
        position: 'absolute', top: 48, right: 0,
        width: 340, maxHeight: 400,
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 10, boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
        display: 'flex', flexDirection: 'column',
        zIndex: 9999, overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div style={{
        padding: '10px 14px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexShrink: 0,
      }}>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 600, color: 'var(--fg1)' }}>
          Notifications
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          {notifications.length > 0 && (
            <>
              <button onClick={onMarkAllRead} style={{
                fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg4)',
                background: 'none', border: 'none', cursor: 'pointer', padding: 0,
              }}>
                Mark all read
              </button>
              <span style={{ color: 'var(--border-md)' }}>·</span>
              <button onClick={onClearAll} style={{
                fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg4)',
                background: 'none', border: 'none', cursor: 'pointer', padding: 0,
              }}>
                Clear all
              </button>
            </>
          )}
        </div>
      </div>

      {/* List */}
      <div style={{ overflowY: 'auto', flex: 1 }}>
        {notifications.length === 0 ? (
          <div style={{
            padding: '28px 16px', textAlign: 'center',
            fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)',
          }}>
            No notifications
          </div>
        ) : (
          notifications.map(n => (
            <div
              key={n.id}
              style={{
                padding: '10px 14px',
                borderBottom: '1px solid var(--border)',
                background: n.read ? 'transparent' : 'var(--bg-subtle)',
                display: 'flex', gap: 10, alignItems: 'flex-start',
              }}
            >
              <div style={{ marginTop: 1, flexShrink: 0 }}>{NOTIF_ICON[n.type]}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 600,
                  color: 'var(--fg1)', marginBottom: 2,
                }}>
                  {n.title}
                </div>
                <div style={{
                  fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--fg3)',
                  lineHeight: 1.45, wordBreak: 'break-word',
                }}>
                  {n.body}
                </div>
                <div style={{
                  fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)',
                  marginTop: 4, letterSpacing: '0.3px',
                }}>
                  {formatAge(n.timestamp)}
                </div>
              </div>
              <button
                onClick={() => onDismiss(n.id)}
                aria-label="Dismiss"
                style={{
                  flexShrink: 0, background: 'none', border: 'none',
                  cursor: 'pointer', color: 'var(--fg4)', padding: 2,
                  display: 'flex', alignItems: 'center',
                }}
              >
                <X size={12} strokeWidth={2} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function StatusBanner({
  dark,
  onToggleDark,
  dotState = 'idle',
  banner,
  lastUpdated,
  databaseCount,
}: Props) {
  const showStats = !!banner;
  const queueTotal = banner ? banner.queued + banner.reading : 0;
  const [bellOpen, setBellOpen] = useState(false);
  const { notifications, unreadCount, markAllRead, dismiss, clearAll } = useNotifications();

  // Activity label — reading page shows sync age when idle; everywhere shows Working/Error when busy
  let activityLabel = '';
  if (dotState === 'working') activityLabel = 'Working…';
  else if (dotState === 'error') activityLabel = 'Error';
  else if (dotState === 'done' && !lastUpdated) activityLabel = 'Saved';
  else if (lastUpdated) activityLabel = `Synced ${formatAge(lastUpdated)}`;

  function handleBellClick() {
    if (!bellOpen) markAllRead();
    setBellOpen(o => !o);
  }

  return (
    <div style={{
      height: 48,
      background: 'var(--bg-subtle)',
      borderBottom: '1px solid var(--border)',
      padding: '0 24px',
      display: 'flex',
      alignItems: 'center',
      gap: 24,
      flexShrink: 0,
      position: 'relative',
    }}>
      {/* Reading-page stats */}
      {showStats && (
        <>
          <Stat label="Queue" value={queueTotal} />
          <Stat label="Database" value={databaseCount ?? '—'} />
          <Stat label="Done" value={banner!.done} />
        </>
      )}

      <div style={{ flex: 1 }} />

      {/* Notification bell */}
      <div style={{ position: 'relative' }}>
        <button
          onClick={handleBellClick}
          aria-label="Notifications"
          style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            width: 28, height: 28, borderRadius: 9999,
            background: 'transparent', border: '1px solid var(--border-md)',
            cursor: 'pointer', color: 'var(--fg4)', position: 'relative',
          }}
        >
          <Bell size={12} strokeWidth={2} />
          {unreadCount > 0 && (
            <span style={{
              position: 'absolute', top: -4, right: -4,
              background: '#E53535', color: '#fff',
              borderRadius: 9999, minWidth: 14, height: 14,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--sans)', fontSize: 9, fontWeight: 700,
              padding: '0 3px', lineHeight: 1,
            }}>
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>

        {bellOpen && (
          <NotificationDropdown
            notifications={notifications}
            onDismiss={dismiss}
            onMarkAllRead={markAllRead}
            onClearAll={clearAll}
            onClose={() => setBellOpen(false)}
          />
        )}
      </div>

      {/* Dark mode toggle */}
      <button
        onClick={onToggleDark}
        aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          padding: '3px 10px', border: '1px solid var(--border-md)',
          borderRadius: 9999, background: 'transparent',
          cursor: 'pointer', color: 'var(--fg4)',
        }}
      >
        {dark ? <Sun size={12} strokeWidth={2} /> : <Moon size={12} strokeWidth={2} />}
        <span style={{
          fontFamily: 'var(--mono)', fontSize: 10,
          textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--fg4)',
        }}>
          {dark ? 'Light' : 'Dark'}
        </span>
      </button>

      {/* Activity label + status pill */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {activityLabel && (
          <span style={{
            fontFamily: 'var(--mono)', fontSize: 10,
            textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--fg4)',
          }}>
            {activityLabel}
          </span>
        )}
        <div style={{
          height: 24, display: 'inline-flex', alignItems: 'center',
          padding: '0 9px', gap: 6, borderRadius: 9999,
          border: '1.5px solid var(--logo-border)', flexShrink: 0,
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: DOT_COLOR[dotState], flexShrink: 0,
            animation: DOT_ANIM[dotState],
          }} />
          <span style={{
            fontFamily: 'var(--sans)', fontSize: 11.5, fontWeight: 600,
            color: 'var(--fg1)', letterSpacing: '-0.2px', lineHeight: 1,
          }}>
            docent
          </span>
        </div>
      </div>
    </div>
  );
}
