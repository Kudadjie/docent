// Docent App — Sidebar component
// Left navigation: logo, primary nav, library list, user footer

// dotStatus: 'idle' | 'working' | 'error' | 'done'
const LogoDot = ({ status = 'idle' }) => {
  const base = {
    width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
    animation: 'none',
  };
  const states = {
    idle:    { background: '#18E299' },
    working: { background: '#F5A623', animation: 'docentBlink 1s step-end infinite' },
    error:   { background: '#E53535', animation: 'docentBlink 0.7s step-end infinite' },
    done:    { background: '#18E299', animation: 'docentDone 0.5s ease-in-out 3' },
  };
  return <span style={{ ...base, ...states[status] }} />;
};

const Sidebar = ({ activeSection, onNavigate, papers, onSelectPaper, activePaperId, dotStatus = 'idle' }) => {
  const navItems = [
    { id: 'chat', label: 'Ask Docent', icon: <ChatIcon /> },
    { id: 'library', label: 'My library', icon: <LibraryIcon /> },
    { id: 'review', label: 'Lit review', icon: <ReviewIcon /> },
    { id: 'citations', label: 'Citations', icon: <CitationsIcon /> },
  ];

  return (
    <aside style={sidebarStyles.root}>
      {/* Logo */}
      <div style={sidebarStyles.logoRow}>
        <div style={sidebarStyles.logoPill}>
          <LogoDot status={dotStatus} />
          <span style={sidebarStyles.logoText}>docent</span>
        </div>
        <span style={sidebarStyles.betaBadge}>Beta</span>
      </div>

      {/* Primary nav */}
      <nav style={sidebarStyles.nav}>
        {navItems.map(item => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            style={{
              ...sidebarStyles.navItem,
              ...(activeSection === item.id ? sidebarStyles.navItemActive : {}),
            }}
          >
            <span style={sidebarStyles.navIcon}>{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      {/* Library section */}
      <div style={sidebarStyles.section}>
        <div style={sidebarStyles.sectionLabel}>Recent papers</div>
        {papers.map(paper => (
          <button
            key={paper.id}
            onClick={() => onSelectPaper(paper.id)}
            style={{
              ...sidebarStyles.paperItem,
              ...(activePaperId === paper.id ? sidebarStyles.paperItemActive : {}),
            }}
          >
            <div style={sidebarStyles.paperTitle}>{paper.title}</div>
            <div style={sidebarStyles.paperMeta}>{paper.author} · {paper.year}</div>
          </button>
        ))}
        <button style={sidebarStyles.addPaper} onClick={() => onNavigate('upload')}>
          <span style={{ marginRight: 6 }}>+</span> Add paper
        </button>
      </div>

      {/* User footer */}
      <div style={sidebarStyles.footer}>
        <div style={sidebarStyles.avatar}>A</div>
        <div style={sidebarStyles.footerInfo}>
          <div style={sidebarStyles.footerName}>Alex Rivera</div>
          <div style={sidebarStyles.footerRole}>PhD · Cognitive Science</div>
        </div>
      </div>
    </aside>
  );
};

// Icons (stroke, lucide-style)
const ChatIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
);
const LibraryIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
  </svg>
);
const ReviewIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
  </svg>
);
const CitationsIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z"/>
    <path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/>
  </svg>
);

const sidebarStyles = {
  root: {
    width: 232,
    flexShrink: 0,
    height: '100%',
    background: '#fafafa',
    borderRight: '1px solid rgba(0,0,0,0.06)',
    display: 'flex',
    flexDirection: 'column',
    padding: '16px 12px',
    gap: 0,
    overflowY: 'auto',
  },
  logoRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '4px 8px 16px',
    borderBottom: '1px solid rgba(0,0,0,0.05)',
    marginBottom: 8,
  },
  logoPill: {
    height: 26,
    background: '#fff',
    border: '1.5px solid #0d0d0d',
    borderRadius: 9999,
    display: 'flex',
    alignItems: 'center',
    padding: '0 10px',
    gap: 6,
  },
  logoDot: {
    width: 6,
    height: 6,
    background: '#18E299',
    borderRadius: '50%',
    flexShrink: 0,
  },
  logoText: {
    fontSize: 13,
    fontWeight: 600,
    letterSpacing: '-0.2px',
    color: '#0d0d0d',
  },
  betaBadge: {
    fontFamily: "'Geist Mono', monospace",
    fontSize: 9,
    fontWeight: 600,
    letterSpacing: '0.5px',
    textTransform: 'uppercase',
    background: '#d4fae8',
    color: '#0fa76e',
    padding: '2px 6px',
    borderRadius: 9999,
    marginLeft: 'auto',
  },
  nav: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    marginBottom: 20,
  },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '7px 10px',
    borderRadius: 8,
    border: 'none',
    background: 'transparent',
    color: '#555',
    fontSize: 13.5,
    fontWeight: 500,
    fontFamily: "'Inter', sans-serif",
    cursor: 'pointer',
    textAlign: 'left',
    transition: 'background 0.1s, color 0.1s',
  },
  navItemActive: {
    background: '#fff',
    color: '#0d0d0d',
    boxShadow: 'rgba(0,0,0,0.04) 0px 1px 3px',
    border: '1px solid rgba(0,0,0,0.05)',
  },
  navIcon: { opacity: 0.7, display: 'flex', alignItems: 'center' },
  section: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: 500,
    letterSpacing: '0.5px',
    textTransform: 'uppercase',
    color: '#999',
    padding: '0 10px 6px',
    fontFamily: "'Geist Mono', monospace",
  },
  paperItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    padding: '8px 10px',
    borderRadius: 8,
    border: 'none',
    background: 'transparent',
    cursor: 'pointer',
    textAlign: 'left',
    transition: 'background 0.1s',
  },
  paperItemActive: {
    background: '#fff',
    boxShadow: 'rgba(0,0,0,0.04) 0px 1px 3px',
    border: '1px solid rgba(0,0,0,0.05)',
  },
  paperTitle: {
    fontSize: 12.5,
    fontWeight: 500,
    color: '#0d0d0d',
    lineHeight: 1.4,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    maxWidth: 180,
  },
  paperMeta: {
    fontSize: 11,
    color: '#999',
  },
  addPaper: {
    display: 'flex',
    alignItems: 'center',
    padding: '6px 10px',
    borderRadius: 8,
    border: '1px dashed rgba(0,0,0,0.12)',
    background: 'transparent',
    color: '#888',
    fontSize: 12.5,
    fontWeight: 500,
    fontFamily: "'Inter', sans-serif",
    cursor: 'pointer',
    marginTop: 4,
    transition: 'border-color 0.1s, color 0.1s',
  },
  footer: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '14px 8px 4px',
    borderTop: '1px solid rgba(0,0,0,0.05)',
    marginTop: 12,
  },
  avatar: {
    width: 30,
    height: 30,
    borderRadius: '50%',
    background: '#18E299',
    color: '#0d0d0d',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 13,
    fontWeight: 600,
    flexShrink: 0,
  },
  footerInfo: { display: 'flex', flexDirection: 'column', gap: 1 },
  footerName: { fontSize: 12.5, fontWeight: 600, color: '#0d0d0d' },
  footerRole: { fontSize: 11, color: '#888' },
};

Object.assign(window, { Sidebar });
