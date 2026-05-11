// Docent App — DocumentPanel component
// Right panel: paper reader with metadata, AI annotation highlights

const DocumentPanel = ({ paper, onClose }) => {
  const [activeTab, setActiveTab] = React.useState('summary');

  if (!paper) return (
    <div style={docStyles.empty}>
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="1.5">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14,2 14,8 20,8"/>
      </svg>
      <div style={docStyles.emptyText}>Select a paper to view details</div>
    </div>
  );

  const tabs = [
    { id: 'summary', label: 'Summary' },
    { id: 'key-points', label: 'Key points' },
    { id: 'citations', label: 'Citations' },
  ];

  return (
    <div style={docStyles.root}>
      {/* Header */}
      <div style={docStyles.header}>
        <div style={docStyles.headerTop}>
          <span style={docStyles.fileType}>PDF</span>
          <button onClick={onClose} style={docStyles.closeBtn}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div style={docStyles.title}>{paper.title}</div>
        <div style={docStyles.meta}>{paper.author} · {paper.year} · {paper.journal}</div>
        <div style={docStyles.tags}>
          {paper.tags && paper.tags.map(t => (
            <span key={t} style={docStyles.tag}>{t}</span>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div style={docStyles.tabs}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{ ...docStyles.tab, ...(activeTab === tab.id ? docStyles.tabActive : {}) }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={docStyles.content}>
        {activeTab === 'summary' && <SummaryTab paper={paper} />}
        {activeTab === 'key-points' && <KeyPointsTab paper={paper} />}
        {activeTab === 'citations' && <CitationsTab paper={paper} />}
      </div>
    </div>
  );
};

const SummaryTab = ({ paper }) => (
  <div style={docStyles.tabContent}>
    <div style={docStyles.aiLabel}>Docent summary</div>
    <p style={docStyles.summaryText}>{paper.summary}</p>
    <div style={docStyles.statRow}>
      <Stat label="Citations" value={paper.citationCount || '—'} />
      <Stat label="Pages" value={paper.pages || '—'} />
      <Stat label="Read time" value={paper.readTime || '—'} />
    </div>
  </div>
);

const KeyPointsTab = ({ paper }) => (
  <div style={docStyles.tabContent}>
    <div style={docStyles.aiLabel}>Key findings</div>
    {(paper.keyPoints || []).map((point, i) => (
      <div key={i} style={docStyles.keyPoint}>
        <div style={docStyles.keyPointNum}>{i + 1}</div>
        <div style={docStyles.keyPointText}>{point}</div>
      </div>
    ))}
  </div>
);

const CitationsTab = ({ paper }) => (
  <div style={docStyles.tabContent}>
    <div style={docStyles.aiLabel}>Referenced works</div>
    {(paper.references || []).map((ref, i) => (
      <div key={i} style={docStyles.refItem}>
        <div style={docStyles.refTitle}>{ref.title}</div>
        <div style={docStyles.refMeta}>{ref.author} · {ref.year}</div>
      </div>
    ))}
  </div>
);

const Stat = ({ label, value }) => (
  <div style={docStyles.stat}>
    <div style={docStyles.statValue}>{value}</div>
    <div style={docStyles.statLabel}>{label}</div>
  </div>
);

const docStyles = {
  root: {
    width: 300,
    flexShrink: 0,
    height: '100%',
    background: '#fff',
    borderLeft: '1px solid rgba(0,0,0,0.06)',
    display: 'flex',
    flexDirection: 'column',
    overflowY: 'auto',
  },
  empty: {
    width: 300,
    flexShrink: 0,
    height: '100%',
    background: '#fff',
    borderLeft: '1px solid rgba(0,0,0,0.06)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    color: '#bbb',
  },
  emptyText: { fontSize: 13, color: '#ccc' },
  header: {
    padding: '16px 16px 12px',
    borderBottom: '1px solid rgba(0,0,0,0.05)',
  },
  headerTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  fileType: {
    fontFamily: "'Geist Mono', monospace",
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: '0.5px',
    textTransform: 'uppercase',
    background: '#f5f5f5',
    color: '#666',
    padding: '2px 7px',
    borderRadius: 4,
  },
  closeBtn: {
    background: 'transparent',
    border: 'none',
    color: '#888',
    cursor: 'pointer',
    padding: 4,
    borderRadius: 6,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 14,
    fontWeight: 600,
    letterSpacing: '-0.2px',
    color: '#0d0d0d',
    lineHeight: 1.4,
    marginBottom: 5,
  },
  meta: { fontSize: 11.5, color: '#888', marginBottom: 8 },
  tags: { display: 'flex', flexWrap: 'wrap', gap: 5 },
  tag: {
    fontSize: 11,
    color: '#555',
    background: '#f5f5f5',
    padding: '2px 8px',
    borderRadius: 9999,
    border: '1px solid rgba(0,0,0,0.05)',
  },
  tabs: {
    display: 'flex',
    padding: '0 16px',
    borderBottom: '1px solid rgba(0,0,0,0.05)',
    gap: 0,
  },
  tab: {
    fontFamily: "'Inter', sans-serif",
    fontSize: 12.5,
    fontWeight: 500,
    color: '#888',
    background: 'transparent',
    border: 'none',
    borderBottom: '2px solid transparent',
    padding: '10px 10px',
    cursor: 'pointer',
    transition: 'color 0.15s',
  },
  tabActive: { color: '#0d0d0d', borderBottomColor: '#18E299' },
  content: { flex: 1, overflowY: 'auto' },
  tabContent: { padding: '16px' },
  aiLabel: {
    fontFamily: "'Geist Mono', monospace",
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: '0.5px',
    textTransform: 'uppercase',
    color: '#0fa76e',
    marginBottom: 10,
  },
  summaryText: { fontSize: 13, lineHeight: 1.65, color: '#333' },
  statRow: { display: 'flex', gap: 0, marginTop: 16, borderTop: '1px solid rgba(0,0,0,0.05)', paddingTop: 14 },
  stat: { flex: 1, textAlign: 'center' },
  statValue: { fontSize: 18, fontWeight: 600, letterSpacing: '-0.3px', color: '#0d0d0d' },
  statLabel: { fontSize: 11, color: '#999', marginTop: 2, textTransform: 'uppercase', letterSpacing: '0.4px', fontFamily: "'Geist Mono', monospace" },
  keyPoint: { display: 'flex', gap: 10, marginBottom: 12 },
  keyPointNum: {
    width: 20,
    height: 20,
    background: '#18E299',
    borderRadius: 5,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 11,
    fontWeight: 600,
    color: '#0d0d0d',
    flexShrink: 0,
    marginTop: 1,
  },
  keyPointText: { fontSize: 13, lineHeight: 1.6, color: '#333' },
  refItem: {
    padding: '10px 0',
    borderBottom: '1px solid rgba(0,0,0,0.04)',
  },
  refTitle: { fontSize: 12.5, fontWeight: 500, color: '#0d0d0d', lineHeight: 1.4 },
  refMeta: { fontSize: 11, color: '#888', marginTop: 2 },
};

Object.assign(window, { DocumentPanel });
