import { X, RefreshCw, Info } from 'lucide-react';

interface DbData {
  database_dir: string | null;
  pdfs: string[];
  last_checked: string;
}

interface Props {
  open: boolean;
  dbData: DbData | null;
  dbLoading: boolean;
  refManagerName: string;
  onClose: () => void;
  onRefresh: () => void;
}

export default function DatabaseInspectorModal({ open, dbData, dbLoading, refManagerName, onClose, onRefresh }: Props) {
  if (!open) return null;
  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 50, background: 'var(--overlay)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{ background: 'var(--bg-card)', borderRadius: 12, border: '1px solid var(--border-md)', boxShadow: '0 16px 48px rgba(0,0,0,0.3)', width: '100%', maxWidth: 560, maxHeight: '82vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontFamily: 'var(--sans)', fontSize: 15, fontWeight: 600, color: 'var(--fg1)' }}>Watch folder</div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg4)', marginTop: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {dbData?.database_dir ?? 'Not configured'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
            <button
              onClick={onRefresh}
              disabled={dbLoading}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 6, border: '1px solid var(--border-md)', background: 'transparent', color: 'var(--fg3)', fontFamily: 'var(--sans)', fontSize: 12, cursor: dbLoading ? 'wait' : 'pointer' }}
            >
              <RefreshCw size={12} strokeWidth={1.5} style={dbLoading ? { animation: 'spin 0.75s linear infinite' } : {}} />
              {dbLoading ? 'Scanning…' : 'Refresh'}
            </button>
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--fg4)', display: 'flex' }}>
              <X size={16} strokeWidth={1.5} />
            </button>
          </div>
        </div>

        <div style={{ padding: '10px 20px', borderBottom: '1px solid var(--border)', background: 'var(--bg-subtle)', display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <Info size={13} strokeWidth={1.5} color="var(--fg4)" style={{ flexShrink: 0, marginTop: 1 }} />
          <span style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.5 }}>
            PDFs dropped here are auto-imported by {refManagerName}. Docent counts files but cannot reliably match filenames to queue entries — check {refManagerName} to see which entries have PDFs attached.
          </span>
        </div>

        <div style={{ padding: '10px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 700, color: 'var(--fg1)' }}>
            {dbData?.pdfs.length ?? '—'}
          </span>
          <span style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)' }}>PDF{(dbData?.pdfs.length ?? 0) !== 1 ? 's' : ''} in folder</span>
          {dbData?.last_checked && (
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', marginLeft: 'auto' }}>
              checked {new Date(dbData.last_checked).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>

        <div style={{ overflowY: 'auto', flex: 1 }}>
          {dbLoading && !dbData && (
            <div style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--fg4)', fontFamily: 'var(--sans)', fontSize: 13 }}>Scanning folder…</div>
          )}
          {!dbData?.database_dir && !dbLoading && (
            <div style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--fg4)', fontFamily: 'var(--sans)', fontSize: 13 }}>
              No watch folder configured — set one in Settings → Reading.
            </div>
          )}
          {dbData?.pdfs.length === 0 && dbData.database_dir && (
            <div style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--fg4)', fontFamily: 'var(--sans)', fontSize: 13 }}>
              No PDFs found in this folder.
            </div>
          )}
          {(dbData?.pdfs ?? []).map((pdf, i) => (
            <div
              key={pdf}
              style={{
                padding: '7px 20px',
                borderBottom: '1px solid var(--border)',
                display: 'flex', alignItems: 'center', gap: 10,
                background: i % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.015)',
              }}
            >
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--fg4)', minWidth: 28, textAlign: 'right', flexShrink: 0 }}>{i + 1}</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{pdf}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
