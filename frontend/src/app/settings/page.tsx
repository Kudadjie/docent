'use client';

import { useState, useEffect, useRef } from 'react';
import { Settings, Trash2, BookOpen, RefreshCw, Activity, Key, Zap, FlaskConical, RotateCcw } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import StatusBanner, { type DotState } from '@/components/StatusBanner';
import Toast, { type ToastData } from '@/components/Toast';
import { useDarkMode } from '@/hooks/useDarkMode';
import { useNotifications } from '@/lib/notifications';
import { useTour } from '@/hooks/useTour';
import { TOUR_KEYS, TOUR_LABELS, tourHasSeen, tourReset, tourResetAll } from '@/lib/tour';
import { extractMessage } from '@/lib/toast-utils';
import ConfigRow from '@/components/settings/ConfigRow';
import SecretKeyRow from '@/components/settings/SecretKeyRow';
import TavilyUsageWidget from '@/components/settings/TavilyUsageWidget';
import { DoctorStatusBadge, SectionCard, KeyGroup, type DoctorCheck } from '@/components/settings/SettingsPrimitives';
import OpenCodeSection from '@/components/settings/OpenCodeSection';
import NotebookLMSection from '@/components/settings/NotebookLMSection';
import BackupRestoreSection from '@/components/settings/BackupRestoreSection';

interface ReadingConfig {
  database_dir: string | null;
  queue_collection: string;
  reference_manager: string;
  zotero_api_key: string | null;
  zotero_library_id: string | null;
  zotero_library_type: string;
  output_dir: string | null;
}

interface ResearchConfig {
  tavily_api_key: string | null;
  semantic_scholar_api_key: string | null;
  alphaxiv_api_key: string | null;
  groq_api_key: string | null;
  feynman_model: string | null;
}

interface ConfigData {
  reading: ReadingConfig;
  research: ResearchConfig;
}

const RESEARCH_KEY_FIELDS: {
  key: keyof ResearchConfig;
  label: string;
  description: string;
  placeholder: string;
}[] = [
  {
    key: 'tavily_api_key',
    label: 'Tavily',
    description: 'Web search for research workflows. Free tier: 1,000 calls/month. Get a key at app.tavily.com — no credit card needed.',
    placeholder: 'tvly-...',
  },
  {
    key: 'alphaxiv_api_key',
    label: 'alphaXiv',
    description: 'Optional — upgrades Search papers and Get paper with AI overviews, topic tags, and GitHub links. Without it, both actions fall back to the free arXiv API automatically. Free key at alphaxiv.org/settings.',
    placeholder: 'ax-...',
  },
  {
    key: 'semantic_scholar_api_key',
    label: 'Semantic Scholar',
    description: 'Optional — raises API rate limits for scholarly search. api.semanticscholar.org',
    placeholder: 'your-key',
  },
  {
    key: 'groq_api_key',
    label: 'Groq',
    description: 'Fast AI backend for the Groq backend option. Free tier at console.groq.com.',
    placeholder: 'gsk_...',
  },
];

export default function SettingsPage() {
  const { dark, toggleDark } = useDarkMode();
  const { addNotification } = useNotifications();

  useTour('settings', [
    {
      popover: {
        title: 'Settings',
        description: "Configure everything about how Docent works — your reference manager connection, AI API keys, cloud backup, and system health.",
      },
    },
    {
      popover: {
        title: 'Reading configuration',
        description: 'Choose your reference manager (Mendeley or Zotero), set the collection name to sync from, and point Docent at your local PDF folder. Your library is read-only — Docent never modifies it.',
      },
    },
    {
      popover: {
        title: 'API keys',
        description: 'Add keys for research backends: Tavily for web search, alphaXiv to enhance paper search with AI overviews (optional — arXiv works without it), Groq for AI synthesis. Each key unlocks or upgrades a Studio capability.',
      },
    },
    {
      popover: {
        title: 'Health check & Backup',
        description: "System health checks that your core dependencies (Python, Feynman, NotebookLM, etc.) are installed and working. Backup lets you save your queue and research history to Google Drive.",
      },
    },
  ]);

  const [tourSeenMap, setTourSeenMap] = useState<Record<string, boolean>>(() => {
    const map: Record<string, boolean> = {};
    TOUR_KEYS.forEach(k => { map[k] = tourHasSeen(k); });
    return map;
  });

  function handleTourReset(key: string) {
    tourReset(key as Parameters<typeof tourReset>[0]);
    setTourSeenMap(prev => ({ ...prev, [key]: false }));
    setToast({ type: 'success', message: `Tour reset — visit ${TOUR_LABELS[key as keyof typeof TOUR_LABELS]} to start the walkthrough.` });
  }

  function handleTourResetAll() {
    tourResetAll();
    const map: Record<string, boolean> = {};
    TOUR_KEYS.forEach(k => { map[k] = false; });
    setTourSeenMap(map);
    setToast({ type: 'success', message: 'All tours reset — visit each page to see the walkthrough.' });
  }

  const [config, setConfig] = useState<ConfigData | null>(null);
  const [toast, setToast] = useState<ToastData | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [doctorChecks, setDoctorChecks] = useState<DoctorCheck[] | null>(null);
  const [loadingDoctor, setLoadingDoctor] = useState(false);
  const [dotState, setDotState] = useState<DotState>('idle');

  const dotResetRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function signalDot(state: DotState) {
    setDotState(state);
    if (dotResetRef.current) clearTimeout(dotResetRef.current);
    if (state === 'done' || state === 'error') {
      dotResetRef.current = setTimeout(() => setDotState('idle'), 2000);
    }
  }

  async function runDoctor() {
    setLoadingDoctor(true);
    signalDot('working');
    try {
      const res = await fetch('/api/doctor');
      const data = await res.json() as DoctorCheck[];
      setDoctorChecks(data);
      signalDot('done');

      const issues = data.filter(c => c.status === 'FAIL' || c.status === 'WARN');
      if (issues.length > 0) {
        addNotification({
          type: 'update',
          title: `${issues.length} health ${issues.length === 1 ? 'issue' : 'issues'} found`,
          body: issues.map(c => c.label).join(', '),
        });
      }
    } catch {
      setDoctorChecks([]);
      signalDot('error');
    } finally {
      setLoadingDoctor(false);
    }
  }

  /* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
  useEffect(() => {
    fetch('/api/config')
      .then(r => r.json())
      .then((d: ConfigData) => setConfig(d))
      .catch(() => {});
    runDoctor();
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */

  const [readingHighlight, setReadingHighlight] = useState(false);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('from') !== 'rm-setup') return;
    window.history.replaceState(null, '', window.location.pathname);
    const timer = setTimeout(() => {
      document.getElementById('section-reading')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setReadingHighlight(true);
      setTimeout(() => setReadingHighlight(false), 1800);
    }, 300);
    return () => clearTimeout(timer);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
        const clean = extractMessage((body.error ?? 'Unknown error').replace(/\x1b\[[0-9;]*m/g, '').trim());
        setToast({ type: 'error', message: `Could not save: ${clean.slice(0, 120)}` });
        signalDot('error');
      } else {
        if (body.reading) setConfig(c => c ? { ...c, reading: body.reading! } : c);
        setToast({ type: 'success', message: key === 'zotero_api_key' ? 'Saved Zotero API key.' : `Saved reading.${key}.` });
        signalDot('done');
      }
    } catch {
      setToast({ type: 'error', message: 'Network error.' });
      signalDot('error');
    }
  }

  async function handleSaveResearch(key: keyof ResearchConfig, value: string) {
    signalDot('working');
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ section: 'research', key, value }),
      });
      const body = await res.json() as { ok: boolean; research?: ResearchConfig; error?: string };
      if (!res.ok || !body.ok) {
        const clean = extractMessage((body.error ?? 'Unknown error').replace(/\x1b\[[0-9;]*m/g, '').trim());
        setToast({ type: 'error', message: `Could not save: ${clean.slice(0, 120)}` });
        signalDot('error');
      } else {
        if (body.research) setConfig(c => c ? { ...c, research: body.research! } : c);
        setToast({ type: 'success', message: `Saved ${key.replace(/_api_key$/, '')} key.` });
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
        body: JSON.stringify({ action: 'queue-clear', confirmed: true }),
      });
      const body = await res.json().catch(() => ({})) as Record<string, string>;
      if (!res.ok) {
        const clean = extractMessage((body.error ?? body.stderr ?? 'Unknown error').replace(/\x1b\[[0-9;]*m/g, '').trim());
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

  const rc = config?.reading;
  const res = config?.research;

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar active="settings" queueCount={0} dark={dark} />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <StatusBanner dark={dark} onToggleDark={toggleDark} dotState={dotState} />

        <div style={{ flex: 1, overflowY: 'auto', position: 'relative',
          backgroundImage: 'var(--hero-grad)',
          backgroundRepeat: 'no-repeat',
          backgroundSize: '100% 100%',
          backgroundAttachment: 'local',
        }}>
          {/* Header */}
          <div style={{ position: 'relative', padding: '28px 32px 24px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <Settings size={16} strokeWidth={1.5} color="#0fa76e" />
              <h1 style={{
                fontFamily: 'var(--sans)', fontSize: 18, fontWeight: 600,
                letterSpacing: '-0.3px', color: 'var(--fg1)', margin: 0,
              }}>
                Settings
              </h1>
            </div>
            <p style={{ position: 'relative', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)', margin: 0 }}>
              Manage your Docent preferences and data.
            </p>
          </div>

          <div style={{ padding: '32px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, maxWidth: 1100, alignItems: 'start' }}>

            {/* Left column: Reading config + System health */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              <section
                id="section-reading"
                style={{
                  borderRadius: 12,
                  outline: readingHighlight ? '2px solid #14B8A6' : '2px solid transparent',
                  outlineOffset: 3,
                  transition: 'outline-color 0.3s ease',
                }}
              >
              <SectionCard
                accentColor="#14B8A6"
                icon={<BookOpen size={14} strokeWidth={1.5} color="#14B8A6" />}
                title="Reading"
                description="Controls how Docent syncs your reading queue with your reference manager and local paper database."
              >
                {/* Reference manager toggle */}
                <div style={{ padding: '16px 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)', marginBottom: 3 }}>
                    Reference manager
                  </div>
                  <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', lineHeight: 1.5, marginBottom: 10 }}>
                    Docent reads from your library to build the queue. Your data is never modified.
                  </div>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {(['mendeley', 'zotero'] as const).map(rm => {
                      const active = (rc?.reference_manager ?? 'mendeley') === rm;
                      return (
                        <button
                          key={rm}
                          onClick={() => { void handleSaveReading('reference_manager', rm); }}
                          style={{
                            padding: '5px 14px', borderRadius: 6,
                            border: active ? 'none' : '1px solid var(--border-md)',
                            background: active ? '#14B8A6' : 'transparent',
                            color: active ? '#fff' : 'var(--fg3)',
                            fontFamily: 'var(--sans)', fontSize: 12, fontWeight: active ? 600 : 400,
                            cursor: 'pointer',
                          }}
                        >
                          {rm === 'mendeley' ? 'Mendeley' : 'Zotero'}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {(rc?.reference_manager ?? 'mendeley') !== 'zotero' && (
                  <ConfigRow
                    label="Watch folder"
                    description="Mendeley watch folder — PDFs dropped here are auto-imported into your library. Set this to the same folder Mendeley monitors."
                    value={rc?.database_dir ?? null}
                    placeholder="~/Documents/Papers"
                    onSave={v => handleSaveReading('database_dir', v)}
                  />
                )}
                <ConfigRow
                  label="Queue collection"
                  description="Name of the collection to sync from. Must exactly match the collection name in your reference manager."
                  value={rc?.queue_collection ?? null}
                  placeholder="Docent-Queue"
                  onSave={v => handleSaveReading('queue_collection', v)}
                />

                {/* Zotero credentials — shown only when Zotero is the active backend */}
                {rc?.reference_manager === 'zotero' && (
                  <>
                    <SecretKeyRow
                      label="Zotero API key"
                      description="From zotero.org/settings/keys — create a key with read access to your personal library. No OAuth, no browser login."
                      masked={rc.zotero_api_key ?? null}
                      placeholder="your-zotero-key"
                      onSave={v => handleSaveReading('zotero_api_key', v)}
                    />
                    <ConfigRow
                      label="Library ID"
                      description="Your numeric Zotero user ID — visible in the URL at zotero.org/settings/keys (e.g. 1234567)."
                      value={rc.zotero_library_id ?? null}
                      placeholder="1234567"
                      onSave={v => handleSaveReading('zotero_library_id', v)}
                    />
                    <div style={{ padding: '14px 0', borderBottom: '1px solid var(--border)' }}>
                      <div style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)', marginBottom: 3 }}>
                        Library type
                      </div>
                      <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', lineHeight: 1.5, marginBottom: 8 }}>
                        Use <em>User</em> for your personal Zotero library; <em>Group</em> for a shared group library.
                      </div>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {(['user', 'group'] as const).map(lt => {
                          const active = (rc.zotero_library_type ?? 'user') === lt;
                          return (
                            <button
                              key={lt}
                              onClick={() => { void handleSaveReading('zotero_library_type', lt); }}
                              style={{
                                padding: '5px 14px', borderRadius: 6,
                                border: active ? 'none' : '1px solid var(--border-md)',
                                background: active ? '#14B8A6' : 'transparent',
                                color: active ? '#fff' : 'var(--fg3)',
                                fontFamily: 'var(--sans)', fontSize: 12, fontWeight: active ? 600 : 400,
                                cursor: 'pointer',
                              }}
                            >
                              {lt.charAt(0).toUpperCase() + lt.slice(1)}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </>
                )}

                <ConfigRow
                  label="Research output directory"
                  description="Folder where Studio research outputs are saved. Defaults to ~/docent/research/ if not set."
                  value={rc?.output_dir ?? null}
                  placeholder="~/docent/research"
                  onSave={v => handleSaveReading('output_dir', v)}
                />
              </SectionCard>
              </section>

              {/* Studio settings */}
              <SectionCard
                accentColor="#8B5CF6"
                icon={<FlaskConical size={14} strokeWidth={1.5} color="#8B5CF6" />}
                title="Studio"
                description="Controls which AI model Feynman uses when running deep research and literature review tasks."
              >
                <ConfigRow
                  label="Feynman model"
                  description="LiteLLM model string passed to Feynman — e.g. groq/llama-3.3-70b-versatile or anthropic/claude-sonnet-4-5. Leave empty to use Feynman's built-in default."
                  value={res?.feynman_model ?? null}
                  placeholder="groq/llama-3.3-70b-versatile"
                  onSave={v => handleSaveResearch('feynman_model', v)}
                />
              </SectionCard>

              {/* System health */}
              <section>
                <div style={{
                  background: 'var(--bg-card)', border: '1px solid var(--border)',
                  borderRadius: 12, overflow: 'hidden',
                }}>
                  <div style={{
                    padding: '16px 20px 14px', borderBottom: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    background: '#3B82F618',
                  }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                        <Activity size={14} strokeWidth={1.5} color="#3B82F6" />
                        <h2 style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: 'var(--fg1)', margin: 0 }}>
                          System health
                        </h2>
                      </div>
                      <p style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', margin: 0, lineHeight: 1.5 }}>
                        Checks that Docent&apos;s core dependencies are installed and reachable.
                      </p>
                    </div>
                    <button
                      onClick={runDoctor} disabled={loadingDoctor}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        padding: '5px 12px', borderRadius: 7,
                        border: '1px solid var(--border-md)',
                        background: 'transparent', color: 'var(--fg3)',
                        fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
                        cursor: loadingDoctor ? 'default' : 'pointer', opacity: loadingDoctor ? 0.6 : 1,
                      }}
                    >
                      <RefreshCw size={12} strokeWidth={1.5} style={{ animation: loadingDoctor ? 'spin 1s linear infinite' : 'none' }} />
                      {loadingDoctor ? 'Checking…' : 'Refresh'}
                    </button>
                  </div>

                  {doctorChecks === null ? (
                    <div style={{ padding: '28px 20px', textAlign: 'center', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg4)' }}>
                      Checking your environment…
                    </div>
                  ) : doctorChecks.length === 0 ? (
                    <div style={{ padding: '16px 20px', fontFamily: 'var(--sans)', fontSize: 13, color: '#D45656' }}>
                      Could not run health checks.
                    </div>
                  ) : (
                    <>
                      {doctorChecks.map((check, i) => (
                        <div key={check.label} style={{
                          display: 'grid',
                          gridTemplateColumns: '150px 52px 90px 1fr',
                          gap: '0 12px', alignItems: 'start',
                          padding: '11px 20px',
                          borderBottom: i < doctorChecks.length - 1 ? '1px solid var(--border)' : 'none',
                          background: check.status === 'FAIL' ? 'rgba(212,86,86,0.03)'
                            : check.status === 'WARN' ? 'rgba(201,123,0,0.02)' : 'transparent',
                        }}>
                          <span style={{ fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 500, color: 'var(--fg1)', paddingTop: 1 }}>
                            {check.label}
                          </span>
                          <div style={{ paddingTop: 2 }}><DoctorStatusBadge status={check.status} /></div>
                          <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--fg4)', paddingTop: 2, wordBreak: 'break-all' }}>
                            {check.version !== '-' ? check.version : ''}
                          </span>
                          <span style={{
                            fontFamily: 'var(--sans)', fontSize: 11.5, lineHeight: 1.5,
                            color: check.status === 'FAIL' ? '#D45656'
                              : check.status === 'WARN' ? '#C97B00' : 'var(--fg4)',
                          }}>
                            {check.detail !== '-' ? check.detail : ''}
                          </span>
                        </div>
                      ))}
                      {(() => {
                        const issues = doctorChecks.filter(c => c.status === 'FAIL' || c.status === 'WARN').length;
                        const ok = doctorChecks.filter(c => c.status === 'OK').length;
                        return (
                          <div style={{
                            padding: '9px 20px', borderTop: '1px solid var(--border)',
                            background: 'var(--bg-subtle)',
                            fontFamily: 'var(--sans)', fontSize: 11.5,
                            color: issues === 0 ? '#0fa76e' : '#C97B00',
                          }}>
                            {issues === 0 ? `All ${ok} checks passed` : `${issues} ${issues === 1 ? 'issue' : 'issues'} found`}
                          </div>
                        );
                      })()}
                    </>
                  )}
                </div>
              </section>
            </div> {/* end left column */}

            {/* Right column: API keys */}
            <SectionCard
              accentColor="#F59E0B"
              icon={<Key size={14} strokeWidth={1.5} color="#F59E0B" />}
              title="API keys"
              description={<>Keys for research backends and paper search. Stored in <span style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>~/.docent/config.toml</span> — never sent anywhere except the respective provider.</>}
            >
              <KeyGroup label="Search & discovery">
                {RESEARCH_KEY_FIELDS.filter(f => ['tavily_api_key','alphaxiv_api_key','semantic_scholar_api_key'].includes(f.key)).map(f => (
                  <div key={f.key}>
                    <SecretKeyRow label={f.label} description={f.description}
                      masked={res ? (res[f.key] ?? null) : null} placeholder={f.placeholder}
                      onSave={v => handleSaveResearch(f.key, v)} />
                    {f.key === 'tavily_api_key' && (
                      <TavilyUsageWidget keyIsSet={!!(res?.tavily_api_key)} />
                    )}
                  </div>
                ))}
              </KeyGroup>
              <KeyGroup label="AI backends">
                {RESEARCH_KEY_FIELDS.filter(f => !['tavily_api_key','alphaxiv_api_key','semantic_scholar_api_key'].includes(f.key)).map(f => (
                  <SecretKeyRow key={f.key} label={f.label} description={f.description}
                    masked={res ? (res[f.key] ?? null) : null} placeholder={f.placeholder}
                    onSave={v => handleSaveResearch(f.key, v)} />
                ))}
              </KeyGroup>
            </SectionCard>

            {/* OpenCode server */}
            <section style={{ gridColumn: '1 / -1' }}>
              <OpenCodeSection />
            </section>

            {/* NotebookLM auth */}
            <section style={{ gridColumn: '1 / -1' }}>
              <NotebookLMSection />
            </section>

            {/* Backup & Restore */}
            <BackupRestoreSection onSignalDot={signalDot} onToast={setToast} />

            {/* Walkthrough tours — full width */}
            <section style={{ gridColumn: '1 / -1' }}>
              <SectionCard
                accentColor="#06B6D4"
                icon={<Zap size={14} strokeWidth={1.5} color="#06B6D4" />}
                title="Walkthrough tours"
                description="Each page has a guided walkthrough that runs the first time you visit it. Reset individual tours below or restart all of them at once."
              >
                <div style={{ padding: '16px 0' }}>
                  {TOUR_KEYS.map(key => (
                    <div
                      key={key}
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '10px 0', borderBottom: '1px solid var(--border)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg1)' }}>
                          {TOUR_LABELS[key]}
                        </span>
                        <span style={{
                          fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 600,
                          padding: '2px 7px', borderRadius: 9999,
                          background: tourSeenMap[key] ? 'rgba(24,226,153,0.12)' : 'var(--gray100)',
                          color: tourSeenMap[key] ? '#0fa76e' : 'var(--fg4)',
                          textTransform: 'uppercase', letterSpacing: '0.4px',
                        }}>
                          {tourSeenMap[key] ? 'seen' : 'not yet'}
                        </span>
                      </div>
                      <button
                        onClick={() => handleTourReset(key)}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: 5,
                          padding: '4px 12px', borderRadius: 6,
                          border: '1px solid var(--border-md)',
                          background: 'transparent', color: 'var(--fg3)',
                          fontFamily: 'var(--sans)', fontSize: 12,
                          cursor: 'pointer',
                        }}
                      >
                        <RotateCcw size={11} strokeWidth={1.5} />
                        Replay
                      </button>
                    </div>
                  ))}
                  <div style={{ paddingTop: 14 }}>
                    <button
                      onClick={handleTourResetAll}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        padding: '6px 14px', borderRadius: 7,
                        border: '1px solid rgba(139,92,246,0.35)',
                        background: 'rgba(139,92,246,0.07)', color: '#8B5CF6',
                        fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                        cursor: 'pointer',
                      }}
                    >
                      <RotateCcw size={13} strokeWidth={1.5} />
                      Reset all tours
                    </button>
                  </div>
                </div>
              </SectionCard>
            </section>

            {/* Danger zone — full width */}
            <section style={{ gridColumn: '1 / -1' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Trash2 size={13} strokeWidth={1.5} color="#D45656" />
                <h2 style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600, color: '#D45656', margin: 0 }}>
                  Danger zone
                </h2>
              </div>

              <div style={{
                border: '1px solid rgba(212,86,86,0.3)',
                borderRadius: 10,
                padding: '20px 24px',
                background: 'rgba(212,86,86,0.03)',
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24 }}>
                  <div>
                    <div style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 500, color: 'var(--fg1)', marginBottom: 4 }}>
                      Clear reading queue
                    </div>
                    <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.5 }}>
                      Removes all entries from the local queue. Your reference manager library is not affected —
                      you can restore the queue by syncing again on the Reading page.
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
