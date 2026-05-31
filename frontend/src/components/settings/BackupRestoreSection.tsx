'use client';

import { useState, useEffect } from 'react';
import { RefreshCw, HardDriveDownload, CloudUpload, RotateCcw, AlertTriangle, Trash2 } from 'lucide-react';
import type { DotState } from '@/components/StatusBanner';
import type { ToastData } from '@/components/Toast';

interface BackupStatus {
  credentials_configured: boolean;
  deps_installed: boolean;
  token_exists: boolean;
  install_cmd: string | null;
}

interface DriveBackup {
  id: string;
  name: string;
  size_mb: number;
  created: string;
}

function fmtSize(mb: number): string {
  if (mb >= 1) return `${mb.toFixed(1)} MB`;
  const kb = Math.round(mb * 1024);
  return kb > 0 ? `${kb} KB` : '< 1 KB';
}

interface Props {
  onSignalDot: (state: DotState) => void;
  onToast: (toast: ToastData) => void;
}

export default function BackupRestoreSection({ onSignalDot, onToast }: Props) {
  const [backupStatus, setBackupStatus] = useState<BackupStatus | null>(null);
  const [driveBackups, setDriveBackups] = useState<DriveBackup[] | null>(null);
  const [loadingBackups, setLoadingBackups] = useState(false);
  const [backingUp, setBackingUp] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [confirmRestoreId, setConfirmRestoreId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showSetup, setShowSetup] = useState(false);
  const [credentialsText, setCredentialsText] = useState('');
  const [savingCreds, setSavingCreds] = useState(false);
  const [installingDeps, setInstallingDeps] = useState(false);

  useEffect(() => {
    fetch('/api/backup/status').then(r => r.json()).then(setBackupStatus).catch(() => {});
  }, []);

  async function loadDriveBackups() {
    setLoadingBackups(true);
    try {
      const res = await fetch('/api/backup/list');
      const data = await res.json() as { ok: boolean; backups?: DriveBackup[]; error?: string };
      if (data.ok) setDriveBackups(data.backups ?? []);
      else onToast({ type: 'error', message: data.error ?? 'Failed to list backups' });
    } catch { onToast({ type: 'error', message: 'Could not reach backup service' }); }
    finally { setLoadingBackups(false); }
  }

  async function handleBackupToDrive() {
    setBackingUp(true); onSignalDot('working');
    try {
      const res = await fetch('/api/backup/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ local_only: false }) });
      const data = await res.json() as { ok: boolean; archive_name?: string; size_mb?: number; files_excluded?: number; error?: string };
      if (data.ok) {
        const excWarn = (data.files_excluded ?? 0) > 0 ? ` (${data.files_excluded} file(s) >100 MB excluded)` : '';
        onToast({ type: 'success', message: `Backed up to Google Drive — ${fmtSize(data.size_mb ?? 0)}${excWarn}` });
        onSignalDot('done');
        setDriveBackups(null);
      } else {
        onToast({ type: 'error', message: data.error ?? 'Backup failed' });
        onSignalDot('error');
      }
    } catch { onToast({ type: 'error', message: 'Backup request failed' }); onSignalDot('error'); }
    finally { setBackingUp(false); }
  }

  function handleDownloadZip() {
    setDownloading(true);
    const a = document.createElement('a');
    a.href = '/api/backup/download';
    a.click();
    setTimeout(() => setDownloading(false), 3000);
  }

  async function handleRestoreFromDrive(backupId: string, name: string) {
    setRestoringId(backupId); setConfirmRestoreId(null); onSignalDot('working');
    try {
      const res = await fetch('/api/backup/restore', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ backup_id: backupId }) });
      const data = await res.json() as { ok: boolean; restored_from?: string; error?: string };
      if (data.ok) {
        onToast({ type: 'success', message: `Restored from ${data.restored_from ?? name}. Restart docent ui to apply.` });
        onSignalDot('done');
      } else {
        onToast({ type: 'error', message: data.error ?? 'Restore failed' });
        onSignalDot('error');
      }
    } catch { onToast({ type: 'error', message: 'Restore request failed' }); onSignalDot('error'); }
    finally { setRestoringId(null); }
  }

  async function handleInstallDeps() {
    setInstallingDeps(true); onSignalDot('working');
    try {
      const res = await fetch('/api/backup/install-deps', { method: 'POST' });
      const data = await res.json() as { ok: boolean; error?: string };
      if (data.ok) {
        onToast({ type: 'success', message: 'Dependencies installed.' });
        onSignalDot('done');
        fetch('/api/backup/status').then(r => r.json()).then(setBackupStatus).catch(() => {});
      } else {
        onToast({ type: 'error', message: data.error ?? 'Installation failed' });
        onSignalDot('error');
      }
    } catch { onToast({ type: 'error', message: 'Install request failed' }); onSignalDot('error'); }
    finally { setInstallingDeps(false); }
  }

  async function handleDeleteBackup(backupId: string) {
    setDeletingId(backupId);
    try {
      const res = await fetch('/api/backup/delete', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ backup_id: backupId }),
      });
      const data = await res.json() as { ok: boolean; error?: string };
      if (data.ok) {
        setDriveBackups(prev => prev ? prev.filter(b => b.id !== backupId) : null);
        onToast({ type: 'success', message: 'Backup deleted from Google Drive.' });
      } else {
        onToast({ type: 'error', message: data.error ?? 'Delete failed' });
      }
    } catch { onToast({ type: 'error', message: 'Delete request failed' }); }
    finally { setDeletingId(null); }
  }

  async function handleSaveCredentials() {
    if (!credentialsText.trim()) return;
    setSavingCreds(true);
    try {
      const res = await fetch('/api/backup/setup', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credentials_json: credentialsText.trim() }),
      });
      const data = await res.json() as { ok: boolean; error?: string };
      if (data.ok) {
        onToast({ type: 'success', message: 'Credentials saved. Run a backup to authenticate with Google.' });
        setShowSetup(false);
        setCredentialsText('');
        fetch('/api/backup/status').then(r => r.json()).then(setBackupStatus).catch(() => {});
      } else {
        onToast({ type: 'error', message: data.error ?? 'Could not save credentials' });
      }
    } catch { onToast({ type: 'error', message: 'Request failed' }); }
    finally { setSavingCreds(false); }
  }

  return (
    <section style={{ gridColumn: '1 / -1' }}>
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px 14px', borderBottom: '1px solid var(--border)', background: 'linear-gradient(135deg, #3B82F620 0%, transparent 60%)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
              <HardDriveDownload size={14} strokeWidth={1.5} color="#3B82F6" />
              <h2 style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)', margin: 0 }}>Backup & Restore</h2>
            </div>
            <p style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', margin: 0 }}>
              Snapshot your queue, config, and research outputs. Files over 100 MB are excluded.
            </p>
          </div>
        </div>

        <div style={{ padding: '20px' }}>
          {backupStatus && (
            <div style={{ marginBottom: 16, padding: '10px 14px', borderRadius: 8, background: 'var(--bg-subtle)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              {backupStatus.credentials_configured && backupStatus.deps_installed ? (
                <>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#18E299', flexShrink: 0 }} />
                  <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg2)' }}>
                    Google Drive configured{backupStatus.token_exists ? ' · authenticated' : ' · will authenticate on first run'}
                  </span>
                </>
              ) : backupStatus.credentials_configured && !backupStatus.deps_installed ? (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <AlertTriangle size={13} strokeWidth={2} color="#C37D0D" style={{ flexShrink: 0 }} />
                    <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg2)', flex: 1 }}>
                      Credentials found but dependencies missing.
                    </span>
                    <button
                      onClick={handleInstallDeps}
                      disabled={installingDeps}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
                        color: '#fff', background: '#C37D0D',
                        border: 'none', borderRadius: 6,
                        padding: '4px 12px', cursor: installingDeps ? 'wait' : 'pointer',
                        whiteSpace: 'nowrap', flexShrink: 0,
                      }}
                    >
                      <RefreshCw size={11} strokeWidth={2} style={{ animation: installingDeps ? 'spin 1s linear infinite' : 'none' }} />
                      {installingDeps ? 'Installing…' : 'Install now'}
                    </button>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <code style={{
                      flex: 1, fontFamily: 'var(--mono)', fontSize: 11,
                      color: 'var(--fg3)', background: 'var(--gray100)',
                      border: '1px solid var(--border)', borderRadius: 5,
                      padding: '4px 10px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
                    </code>
                    <button
                      onClick={() => navigator.clipboard.writeText('pip install google-api-python-client google-auth-oauthlib google-auth-httplib2').then(() => onToast({ type: 'success', message: 'Copied!' }))}
                      title="Copy to clipboard"
                      style={{ background: 'var(--gray100)', border: '1px solid var(--border)', borderRadius: 5, padding: '4px 8px', cursor: 'pointer', color: 'var(--fg4)', display: 'flex', flexShrink: 0 }}
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--fg4)', flexShrink: 0 }} />
                  <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', flex: 1 }}>
                    Google Drive not configured.
                  </span>
                  <button
                    onClick={() => setShowSetup(s => !s)}
                    style={{ fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500, color: '#3B82F6', background: 'transparent', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 6, padding: '3px 10px', cursor: 'pointer', whiteSpace: 'nowrap' }}
                  >
                    {showSetup ? 'Hide setup' : 'Set up Google Drive'}
                  </button>
                </>
              )}
            </div>
          )}

          {showSetup && (
            <div style={{ marginBottom: 16, border: '1px solid rgba(59,130,246,0.25)', borderRadius: 10, overflow: 'hidden' }}>
              <div style={{ padding: '14px 18px', background: 'rgba(59,130,246,0.04)', borderBottom: '1px solid rgba(59,130,246,0.15)' }}>
                <div style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)', marginBottom: 10 }}>
                  Google Drive — four steps
                </div>
                {[
                  { n: '1', text: <>Go to <a href="https://console.cloud.google.com" target="_blank" rel="noreferrer" style={{ color: '#3B82F6', textDecoration: 'none', fontWeight: 500 }}>console.cloud.google.com</a> → create or select a project → enable the <strong style={{ color: 'var(--fg1)' }}>Google Drive API</strong>.</> },
                  { n: '2', text: <>Credentials → Create Credentials → <strong style={{ color: 'var(--fg1)' }}>OAuth client ID</strong> → Application type: <strong style={{ color: 'var(--fg1)' }}>Desktop app</strong> → Download JSON.</> },
                  { n: '3', text: <><strong style={{ color: 'var(--fg1)' }}>OAuth consent screen</strong> → fill in <strong style={{ color: 'var(--fg1)' }}>App name</strong>, <strong style={{ color: 'var(--fg1)' }}>User support email</strong>, and <strong style={{ color: 'var(--fg1)' }}>Developer contact email</strong> (required — missing any of these causes a Google 500 error). Then under <strong style={{ color: 'var(--fg1)' }}>Audience</strong> click <strong style={{ color: 'var(--fg1)' }}>Publish app</strong>. On first sign-in Google shows an &ldquo;unverified app&rdquo; warning — click <em>Advanced → Go to app</em> to proceed.</> },
                  { n: '4', text: <>Paste the downloaded credentials JSON below and click <strong style={{ color: 'var(--fg1)' }}>Save</strong>. A browser window will open for sign-in on the first backup run.</> },
                ].map(({ n, text }) => (
                  <div key={n} style={{ display: 'flex', gap: 12, marginBottom: 8, alignItems: 'flex-start' }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, color: '#3B82F6', background: 'rgba(59,130,246,0.12)', borderRadius: '50%', width: 20, height: 20, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 }}>{n}</span>
                    <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.55 }}>{text}</span>
                  </div>
                ))}
              </div>
              <div style={{ padding: '14px 18px' }}>
                <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', marginBottom: 8 }}>
                  Paste credentials JSON
                  <span style={{ color: 'var(--fg4)', marginLeft: 8 }}>— or —</span>
                  <label style={{ marginLeft: 8, color: '#3B82F6', cursor: 'pointer', fontSize: 12 }}>
                    choose file
                    <input
                      type="file" accept=".json" style={{ display: 'none' }}
                      onChange={e => {
                        const f = e.target.files?.[0];
                        if (!f) return;
                        const reader = new FileReader();
                        reader.onload = ev => setCredentialsText(ev.target?.result as string ?? '');
                        reader.readAsText(f);
                      }}
                    />
                  </label>
                </div>
                <textarea
                  value={credentialsText}
                  onChange={e => setCredentialsText(e.target.value)}
                  placeholder='{"installed":{"client_id":"...","client_secret":"...",...}}'
                  rows={5}
                  style={{
                    width: '100%', boxSizing: 'border-box',
                    fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)',
                    background: 'var(--bg-subtle)', border: '1px solid var(--border-md)',
                    borderRadius: 7, padding: '10px 12px', resize: 'vertical', outline: 'none',
                  }}
                />
                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <button
                    onClick={handleSaveCredentials}
                    disabled={savingCreds || !credentialsText.trim()}
                    style={{
                      padding: '6px 16px', borderRadius: 7,
                      border: 'none', background: '#3B82F6', color: '#fff',
                      fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                      cursor: (savingCreds || !credentialsText.trim()) ? 'not-allowed' : 'pointer',
                      opacity: !credentialsText.trim() ? 0.5 : 1,
                    }}
                  >
                    {savingCreds ? 'Saving…' : 'Save credentials'}
                  </button>
                  <button
                    onClick={() => { setShowSetup(false); setCredentialsText(''); }}
                    style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid var(--border-md)', background: 'transparent', color: 'var(--fg3)', fontFamily: 'var(--sans)', fontSize: 13, cursor: 'pointer' }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
            <button
              onClick={handleBackupToDrive}
              disabled={backingUp || !backupStatus?.credentials_configured || !backupStatus?.deps_installed}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 7,
                padding: '7px 16px', borderRadius: 8,
                border: '1px solid rgba(59,130,246,0.4)',
                background: 'rgba(59,130,246,0.08)', color: '#3B82F6',
                fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                cursor: (backingUp || !backupStatus?.credentials_configured || !backupStatus?.deps_installed) ? 'not-allowed' : 'pointer',
                opacity: (!backupStatus?.credentials_configured || !backupStatus?.deps_installed) ? 0.5 : 1,
              }}
            >
              <CloudUpload size={14} strokeWidth={1.5} style={{ animation: backingUp ? 'spin 1s linear infinite' : 'none' }} />
              {backingUp ? 'Backing up…' : 'Backup to Drive'}
            </button>

            <button
              onClick={handleDownloadZip}
              disabled={downloading}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 7,
                padding: '7px 16px', borderRadius: 8,
                border: '1px solid var(--border-md)',
                background: 'transparent', color: 'var(--fg2)',
                fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                cursor: downloading ? 'wait' : 'pointer',
              }}
            >
              <HardDriveDownload size={14} strokeWidth={1.5} />
              {downloading ? 'Preparing…' : 'Download local zip'}
            </button>

            {backupStatus?.credentials_configured && backupStatus?.deps_installed && (
              <button
                onClick={() => { if (driveBackups === null) loadDriveBackups(); else setDriveBackups(null); }}
                disabled={loadingBackups}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 7,
                  padding: '7px 16px', borderRadius: 8,
                  border: '1px solid var(--border-md)',
                  background: 'transparent', color: 'var(--fg3)',
                  fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 400,
                  cursor: loadingBackups ? 'wait' : 'pointer',
                }}
              >
                <RefreshCw size={13} strokeWidth={1.5} style={{ animation: loadingBackups ? 'spin 1s linear infinite' : 'none' }} />
                {driveBackups !== null ? 'Hide Drive backups' : 'Show Drive backups'}
              </button>
            )}
          </div>

          {driveBackups !== null && (
            <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
              {driveBackups.length === 0 ? (
                <div style={{ padding: '20px', textAlign: 'center', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg4)' }}>
                  No backups found in Google Drive.
                </div>
              ) : (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto auto', gap: 0, background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border)', padding: '7px 16px' }}>
                    {['Name', 'Size', 'Date', ''].map((h, i) => (
                      <span key={i} style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase', textAlign: i > 1 ? 'right' : 'left', paddingRight: i < 3 ? 16 : 0 }}>{h}</span>
                    ))}
                  </div>
                  {driveBackups.map(b => (
                    <div key={b.id} style={{ display: 'grid', gridTemplateColumns: '1fr auto auto auto', gap: 0, padding: '10px 16px', borderBottom: '1px solid var(--border)', alignItems: 'center' }}>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', paddingRight: 16 }}>{b.name}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg4)', paddingRight: 16, textAlign: 'right' }}>{fmtSize(b.size_mb)}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg4)', paddingRight: 16, textAlign: 'right' }}>{b.created}</span>
                      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                        {confirmRestoreId === b.id ? (
                          <>
                            <button onClick={() => handleRestoreFromDrive(b.id, b.name)} disabled={restoringId === b.id} style={{ fontFamily: 'var(--sans)', fontSize: 11, fontWeight: 600, color: '#fff', background: '#D45656', border: 'none', borderRadius: 5, padding: '3px 10px', cursor: 'pointer' }}>
                              {restoringId === b.id ? 'Restoring…' : 'Confirm'}
                            </button>
                            <button onClick={() => setConfirmRestoreId(null)} style={{ fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg3)', background: 'transparent', border: '1px solid var(--border-md)', borderRadius: 5, padding: '3px 10px', cursor: 'pointer' }}>
                              Cancel
                            </button>
                          </>
                        ) : (
                          <>
                            <button onClick={() => setConfirmRestoreId(b.id)} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg3)', background: 'transparent', border: '1px solid var(--border-md)', borderRadius: 5, padding: '3px 10px', cursor: 'pointer' }}>
                              <RotateCcw size={11} strokeWidth={1.5} />
                              Restore
                            </button>
                            <button
                              onClick={() => handleDeleteBackup(b.id)}
                              disabled={deletingId === b.id}
                              title="Delete from Google Drive"
                              style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 26, height: 26, borderRadius: 5, border: '1px solid var(--border-md)', background: 'transparent', color: deletingId === b.id ? 'var(--fg4)' : '#D45656', cursor: deletingId === b.id ? 'wait' : 'pointer' }}
                            >
                              {deletingId === b.id
                                ? <RefreshCw size={11} strokeWidth={1.5} style={{ animation: 'spin 1s linear infinite' }} />
                                : <Trash2 size={11} strokeWidth={1.5} />}
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
