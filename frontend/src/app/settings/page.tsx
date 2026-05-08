'use client';

import { useState, useEffect, useRef } from 'react';
import { Settings, Trash2, Pencil, Check, X, BookOpen, RefreshCw } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import StatusBanner, { type DotState } from '@/components/StatusBanner';
import Toast, { type ToastData } from '@/components/Toast';
import { useDarkMode } from '@/hooks/useDarkMode';
import { useNotifications } from '@/lib/notifications';

interface ReadingConfig {
  database_dir: string | null;
  queue_collection: string;
}

interface ConfigData {
  reading: ReadingConfig;
}

const READING_FIELDS: {
  key: keyof ReadingConfig;
  label: string;
  description: string;
  placeholder: string;
}[] = [
  {
    key: 'database_dir',
    label: 'Database directory',
    description: 'Local folder where your PDFs are stored. Docent counts PDFs here and uses this path for paper scanning.',
    placeholder: '~/Documents/Papers',
  },
  {
    key: 'queue_collection',
    label: 'Mendeley collection',
    description: 'Name of the Mendeley collection to sync from. Must exactly match the collection name in the Mendeley desktop app.',
    placeholder: 'Docent-Queue',
  },
];

function ConfigRow({
  label,
  description,
  value,
  placeholder,
  onSave,
}: {
  label: string;
  description: string;
  value: string | null;
  placeholder: string;
  onSave: (v: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);

  function startEdit() {
    setDraft(value ?? '');
    setEditing(true);
  }

  async function save() {
    setSaving(true);
    await onSave(draft.trim());
    setSaving(false);
    setEditing(false);
  }

  function cancel() {
    setEditing(false);
    setDraft('');
  }

  return (
    <div style={{
      padding: '16px 0',
      borderBottom: '1px solid var(--border)',
      display: 'grid',
      gridTemplateColumns: '1fr auto',
      gap: '12px 24px',
      alignItems: 'start',
    }}>
      <div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)', marginBottom: 3 }}>
          {label}
        </div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', lineHeight: 1.5 }}>
          {description}
        </div>
        <div style={{ marginTop: 8 }}>
          {editing ? (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input
                autoFocus
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') cancel(); }}
                placeholder={placeholder}
                style={{
                  fontFamily: 'var(--mono)', fontSize: 12,
                  padding: '5px 10px', borderRadius: 6,
                  border: '1px solid #18E299',
                  background: 'var(--bg-card)', color: 'var(--fg1)',
                  outline: 'none', width: 320,
                }}
              />
              <button
                onClick={save}
                disabled={saving}
                aria-label="Save"
                style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  width: 28, height: 28, borderRadius: 6, border: 'none',
                  background: 'rgba(24,226,153,0.15)', color: '#0fa76e',
                  cursor: saving ? 'default' : 'pointer', opacity: saving ? 0.6 : 1,
                }}
              >
                <Check size={14} strokeWidth={2} />
              </button>
              <button
                onClick={cancel}
                aria-label="Cancel"
                style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  width: 28, height: 28, borderRadius: 6, border: 'none',
                  background: 'var(--gray100)', color: 'var(--fg3)',
                  cursor: 'pointer',
                }}
              >
                <X size={14} strokeWidth={2} />
              </button>
            </div>
          ) : (
            <span style={{
              fontFamily: 'var(--mono)', fontSize: 12,
              color: value ? 'var(--fg2)' : 'var(--fg4)',
              fontStyle: value ? 'normal' : 'italic',
            }}>
              {value ?? 'not set'}
            </span>
          )}
        </div>
      </div>

      {!editing && (
        <button
          onClick={startEdit}
          aria-label={`Edit ${label}`}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '5px 10px', borderRadius: 6,
            border: '1px solid var(--border-md)',
            background: 'transparent', color: 'var(--fg3)',
            fontFamily: 'var(--sans)', fontSize: 12,
            cursor: 'pointer', whiteSpace: 'nowrap', marginTop: 2,
          }}
        >
          <Pencil size={12} strokeWidth={1.5} />
          Edit
        </button>
      )}
    </div>
  );
}

interface VersionInfo {
  installed: string | null;
  latest: string | null;
  up_to_date: boolean | null;
  error?: string;
}

interface ToolInfo {
  name: string;
  label: string;
  installed: string | null;
  latest: string | null;
  up_to_date: boolean | null;
  upgrade_cmd: string;
}

export default function SettingsPage() {
  const { dark, toggleDark } = useDarkMode();
  const { addNotification } = useNotifications();
  const [config, setConfig] = useState<ConfigData | null>(null);
  const [toast, setToast] = useState<ToastData | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [versionInfo, setVersionInfo] = useState<VersionInfo | null>(null);
  const [checkingVersion, setCheckingVersion] = useState(false);
  const [toolingInfo, setToolingInfo] = useState<ToolInfo[] | null>(null);
  const [checkingTooling, setCheckingTooling] = useState(false);
  const [dotState, setDotState] = useState<DotState>('idle');
  const dotResetRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Transition dotState and auto-reset to idle after 2s
  function signalDot(state: DotState) {
    setDotState(state);
    if (dotResetRef.current) clearTimeout(dotResetRef.current);
    if (state === 'done' || state === 'error') {
      dotResetRef.current = setTimeout(() => setDotState('idle'), 2000);
    }
  }

  useEffect(() => {
    fetch('/api/config')
      .then(r => r.json())
      .then((d: ConfigData) => setConfig(d))
      .catch(() => {});
  }, []);

  async function handleSaveReading(key: keyof ReadingConfig, value: string) {
    signalDot('working');
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ section: 'reading', key, value }),
      });
      const body = await res.json() as { ok: boolean; reading?: ReadingConfig; error?: string };
      if (!res.ok || !body.ok) {
        const clean = (body.error ?? 'Unknown error').replace(/\x1b\[[0-9;]*m/g, '').trim();
        setToast({ type: 'error', message: `Could not save: ${clean.slice(0, 120)}` });
        signalDot('error');
      } else {
        if (body.reading) setConfig(c => c ? { ...c, reading: body.reading! } : c);
        setToast({ type: 'success', message: `Saved reading.${key}.` });
        signalDot('done');
      }
    } catch {
      setToast({ type: 'error', message: 'Network error.' });
      signalDot('error');
    }
  }

  async function handleClearQueue() {
    setClearing(true);
    signalDot('working');
    try {
      const res = await fetch('/api/actions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'queue-clear' }),
      });
      const body = await res.json().catch(() => ({})) as Record<string, string>;
      if (!res.ok) {
        const clean = (body.error ?? body.stderr ?? 'Unknown error').replace(/\x1b\[[0-9;]*m/g, '').trim();
        setToast({ type: 'error', message: `Clear failed: ${clean.slice(0, 120)}` });
        signalDot('error');
      } else {
        setToast({ type: 'success', message: 'Reading queue cleared.' });
        signalDot('done');
      }
    } catch {
      setToast({ type: 'error', message: 'Network error.' });
      signalDot('error');
    } finally {
      setClearing(false);
      setConfirmClear(false);
    }
  }

  async function checkForUpdates() {
    setCheckingVersion(true);
    signalDot('working');
    try {
      const res = await fetch('/api/version');
      const data = await res.json() as VersionInfo;
      setVersionInfo(data);
      signalDot('done');
      if (data.up_to_date === false && data.latest) {
        addNotification({
          type: 'update',
          title: 'Docent update available',
          body: `v${data.latest} is out (you have v${data.installed ?? '?'}). Run \`pip install -U docent-cli\` to update.`,
        });
      }
    } catch {
      setVersionInfo({ installed: null, latest: null, up_to_date: null, error: 'Network error' });
      signalDot('error');
    } finally {
      setCheckingVersion(false);
    }
  }

  async function checkForToolingUpdates() {
    setCheckingTooling(true);
    signalDot('working');
    try {
      const res = await fetch('/api/tooling');
      const data = await res.json() as ToolInfo[];
      setToolingInfo(data);
      signalDot('done');
      const outdated = data.filter(t => t.up_to_date === false);
      if (outdated.length > 0) {
        outdated.forEach(t => {
          addNotification({
            type: 'update',
            title: `${t.label} update available`,
            body: `v${t.latest} is out (you have v${t.installed ?? '?'}). Run \`${t.upgrade_cmd}\`.`,
          });
        });
      }
    } catch {
      setToolingInfo([]);
      signalDot('error');
    } finally {
      setCheckingTooling(false);
    }
  }

  const rc = config?.reading;

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar active="settings" queueCount={0} dark={dark} />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <StatusBanner dark={dark} onToggleDark={toggleDark} dotState={dotState} />

        {/* Scrollable content */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {/* Header */}
          <div style={{
            padding: '28px 32px 24px',
            borderBottom: '1px solid var(--border)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <Settings size={16} strokeWidth={1.5} color="#0fa76e" />
              <h1 style={{
                fontFamily: 'var(--sans)', fontSize: 18, fontWeight: 600,
                letterSpacing: '-0.3px', color: 'var(--fg1)', margin: 0,
              }}>
                Settings
              </h1>
            </div>
            <p style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)', margin: 0 }}>
              Manage your Docent preferences and data.
            </p>
          </div>

          {/* Content */}
          <div style={{ padding: '32px', maxWidth: 640 }}>

            {/* Reading config */}
            <section style={{ marginBottom: 48 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <BookOpen size={14} strokeWidth={1.5} color="#0fa76e" />
                <h2 style={{
                  fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600,
                  color: 'var(--fg2)', letterSpacing: '0.2px', margin: 0,
                }}>
                  Reading
                </h2>
              </div>
              <p style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', marginBottom: 16 }}>
                Controls how Docent syncs your reading queue with Mendeley and your local paper database.
              </p>

              <div style={{ borderTop: '1px solid var(--border)' }}>
                {READING_FIELDS.map(f => (
                  <ConfigRow
                    key={f.key}
                    label={f.label}
                    description={f.description}
                    value={rc ? (rc[f.key] as string | null) : null}
                    placeholder={f.placeholder}
                    onSave={v => handleSaveReading(f.key, v)}
                  />
                ))}
              </div>
            </section>

            {/* Version */}
            <section style={{ marginBottom: 48 }}>
              <h2 style={{
                fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600,
                color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase',
                margin: '0 0 16px',
              }}>
                Updates
              </h2>

              <div style={{
                border: '1px solid var(--border)',
                borderRadius: 10,
                padding: '20px 24px',
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24 }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{
                      fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 500,
                      color: 'var(--fg1)', marginBottom: 4,
                    }}>
                      Docent version
                    </div>

                    {versionInfo ? (
                      <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.6 }}>
                        {versionInfo.error ? (
                          <span style={{ color: '#D45656' }}>{versionInfo.error}</span>
                        ) : versionInfo.up_to_date ? (
                          <span style={{ color: '#0fa76e' }}>
                            v{versionInfo.installed} — up to date
                          </span>
                        ) : (
                          <>
                            <span>Installed: <span style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>v{versionInfo.installed}</span></span>
                            {versionInfo.latest && (
                              <>
                                {' · '}
                                <span style={{ color: '#C97B00' }}>
                                  v{versionInfo.latest} available
                                </span>
                                <div style={{ marginTop: 6 }}>
                                  Run{' '}
                                  <span style={{
                                    fontFamily: 'var(--mono)', fontSize: 11,
                                    background: 'var(--gray100)', padding: '1px 6px',
                                    borderRadius: 4, border: '1px solid var(--border)',
                                    color: 'var(--fg1)',
                                  }}>
                                    docent update
                                  </span>
                                  {' '}in your terminal, then restart Claude.
                                </div>
                              </>
                            )}
                          </>
                        )}
                      </div>
                    ) : (
                      <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)' }}>
                        Click to check for updates.
                      </div>
                    )}
                  </div>

                  <button
                    onClick={checkForUpdates}
                    disabled={checkingVersion}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      padding: '6px 14px', borderRadius: 7,
                      border: '1px solid var(--border-md)',
                      background: 'transparent', color: 'var(--fg3)',
                      fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                      cursor: checkingVersion ? 'default' : 'pointer',
                      opacity: checkingVersion ? 0.6 : 1, flexShrink: 0,
                    }}
                  >
                    <RefreshCw size={13} strokeWidth={1.5} style={{ animation: checkingVersion ? 'spin 1s linear infinite' : 'none' }} />
                    {checkingVersion ? 'Checking…' : 'Check for updates'}
                  </button>
                </div>
              </div>
            </section>

            {/* Tooling updates */}
            <section style={{ marginBottom: 48 }}>
              <h2 style={{
                fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600,
                color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase',
                margin: '0 0 16px',
              }}>
                Tooling
              </h2>

              <div style={{
                border: '1px solid var(--border)',
                borderRadius: 10,
                padding: '20px 24px',
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24 }}>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{
                      fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 500,
                      color: 'var(--fg1)', marginBottom: 4,
                    }}>
                      Research tooling
                    </div>
                    <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', marginBottom: 10 }}>
                      External tools Docent uses for research workflows.
                    </div>

                    {toolingInfo ? (
                      toolingInfo.length === 0 ? (
                        <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: '#D45656' }}>
                          Could not fetch tooling versions.
                        </span>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                          {toolingInfo.map(t => (
                            <div key={t.name} style={{
                              display: 'flex', alignItems: 'center', gap: 10,
                              padding: '10px 14px', borderRadius: 8,
                              background: 'var(--bg-subtle)',
                              border: '1px solid var(--border)',
                            }}>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <span style={{
                                  fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 600,
                                  color: 'var(--fg1)',
                                }}>
                                  {t.label}
                                </span>
                                <span style={{
                                  fontFamily: 'var(--mono)', fontSize: 10,
                                  color: 'var(--fg4)', marginLeft: 8,
                                }}>
                                  {t.name}
                                </span>
                              </div>
                              <div style={{ fontFamily: 'var(--sans)', fontSize: 12 }}>
                                {t.up_to_date === null ? (
                                  <span style={{ color: 'var(--fg4)' }}>
                                    {t.installed ? `v${t.installed}` : 'not installed'}
                                  </span>
                                ) : t.up_to_date ? (
                                  <span style={{ color: '#0fa76e' }}>v{t.installed} — up to date</span>
                                ) : (
                                  <span style={{ color: '#C97B00' }}>
                                    v{t.installed} → <strong>v{t.latest}</strong> available
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                          {toolingInfo.some(t => t.up_to_date === false) && (
                            <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', marginTop: 4 }}>
                              Run{' '}
                              {toolingInfo.filter(t => t.up_to_date === false).map((t, i, arr) => (
                                <span key={t.name}>
                                  <span style={{
                                    fontFamily: 'var(--mono)', fontSize: 11,
                                    background: 'var(--gray100)', padding: '1px 6px',
                                    borderRadius: 4, border: '1px solid var(--border)',
                                    color: 'var(--fg1)',
                                  }}>
                                    {t.upgrade_cmd}
                                  </span>
                                  {i < arr.length - 1 ? ', ' : ''}
                                </span>
                              ))}{' '}
                              in your terminal.
                            </div>
                          )}
                        </div>
                      )
                    ) : (
                      <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)' }}>
                        Click to check for tooling updates.
                      </div>
                    )}
                  </div>

                  <button
                    onClick={checkForToolingUpdates}
                    disabled={checkingTooling}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      padding: '6px 14px', borderRadius: 7,
                      border: '1px solid var(--border-md)',
                      background: 'transparent', color: 'var(--fg3)',
                      fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                      cursor: checkingTooling ? 'default' : 'pointer',
                      opacity: checkingTooling ? 0.6 : 1, flexShrink: 0,
                    }}
                  >
                    <RefreshCw size={13} strokeWidth={1.5} style={{ animation: checkingTooling ? 'spin 1s linear infinite' : 'none' }} />
                    {checkingTooling ? 'Checking…' : 'Check now'}
                  </button>
                </div>
              </div>
            </section>

            {/* Danger zone */}
            <section>
              <h2 style={{
                fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600,
                color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase',
                margin: '0 0 16px',
              }}>
                Danger Zone
              </h2>

              <div style={{
                border: '1px solid rgba(212,86,86,0.3)',
                borderRadius: 10,
                padding: '20px 24px',
                background: 'rgba(212,86,86,0.03)',
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24 }}>
                  <div>
                    <div style={{
                      fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 500,
                      color: 'var(--fg1)', marginBottom: 4,
                    }}>
                      Clear reading queue
                    </div>
                    <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.5 }}>
                      Removes all entries from the local queue. Your Mendeley library is not affected —
                      you can restore the queue by running{' '}
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)' }}>
                        Sync Mendeley
                      </span>{' '}
                      on the Reading page.
                    </div>
                  </div>

                  {confirmClear ? (
                    <div style={{ display: 'flex', gap: 8, flexShrink: 0, alignItems: 'center' }}>
                      <button
                        onClick={handleClearQueue}
                        disabled={clearing}
                        style={{
                          padding: '6px 14px', borderRadius: 7, border: 'none',
                          background: '#D45656', color: '#fff',
                          fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600,
                          cursor: clearing ? 'default' : 'pointer',
                          opacity: clearing ? 0.6 : 1, whiteSpace: 'nowrap',
                        }}
                      >
                        {clearing ? 'Clearing…' : 'Yes, clear'}
                      </button>
                      <button
                        onClick={() => setConfirmClear(false)}
                        style={{
                          padding: '6px 12px', borderRadius: 7,
                          border: '1px solid var(--border-md)',
                          background: 'transparent', color: 'var(--fg3)',
                          fontFamily: 'var(--sans)', fontSize: 13, cursor: 'pointer',
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmClear(true)}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        padding: '6px 14px', borderRadius: 7,
                        border: '1px solid rgba(212,86,86,0.4)',
                        background: 'transparent', color: '#D45656',
                        fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                        cursor: 'pointer', flexShrink: 0,
                      }}
                    >
                      <Trash2 size={14} strokeWidth={1.5} />
                      Clear queue
                    </button>
                  )}
                </div>
              </div>
            </section>
          </div>
        </div>
      </main>

      {toast && <Toast toast={toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
