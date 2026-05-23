// Docent App — ChatThread component
// Main AI chat area with message list and composer

const ChatThread = ({ messages, onSend, isTyping }) => {
  const [input, setInput] = React.useState('');
  const bottomRef = React.useRef(null);

  React.useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.parentElement.scrollTop = bottomRef.current.offsetTop;
    }
  }, [messages, isTyping]);

  const handleSend = () => {
    if (!input.trim()) return;
    onSend(input.trim());
    setInput('');
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  return (
    <div style={chatStyles.root}>
      {/* Message list */}
      <div style={chatStyles.messages}>
        {messages.length === 0 && <EmptyState />}
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
        {isTyping && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Composer */}
      <div style={chatStyles.composerWrap}>
        <div style={chatStyles.composer}>
          <textarea
            style={chatStyles.textarea}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask about your papers, thesis, methods…"
            rows={1}
          />
          <button
            style={{
              ...chatStyles.sendBtn,
              ...(input.trim() ? chatStyles.sendBtnActive : {}),
            }}
            onClick={handleSend}
            disabled={!input.trim()}
          >
            <SendIcon />
          </button>
        </div>
        <div style={chatStyles.hint}>Press Enter to send · Shift+Enter for new line</div>
      </div>
    </div>
  );
};

const MessageBubble = ({ msg }) => {
  const isUser = msg.role === 'user';
  return (
    <div style={{ ...chatStyles.messageRow, ...(isUser ? chatStyles.messageRowUser : {}) }}>
      {!isUser && (
        <div style={chatStyles.assistantAvatar}>
          <div style={chatStyles.assistantAvatarInner} />
        </div>
      )}
      <div style={{
        ...chatStyles.bubble,
        ...(isUser ? chatStyles.bubbleUser : chatStyles.bubbleAssistant),
      }}>
        {msg.content}
        {msg.sources && msg.sources.length > 0 && (
          <div style={chatStyles.sources}>
            {msg.sources.map((s, i) => (
              <span key={i} style={chatStyles.sourceTag}>{s}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const TypingIndicator = () => (
  <div style={chatStyles.messageRow}>
    <div style={chatStyles.assistantAvatar}><div style={chatStyles.assistantAvatarInner} /></div>
    <div style={{ ...chatStyles.bubble, ...chatStyles.bubbleAssistant }}>
      <div style={chatStyles.dots}>
        <span style={{ ...chatStyles.dot, animationDelay: '0ms' }} />
        <span style={{ ...chatStyles.dot, animationDelay: '150ms' }} />
        <span style={{ ...chatStyles.dot, animationDelay: '300ms' }} />
      </div>
    </div>
  </div>
);

const EmptyState = () => (
  <div style={chatStyles.emptyState}>
    <div style={chatStyles.emptyIcon}>
      <div style={chatStyles.emptyIconMark} />
    </div>
    <div style={chatStyles.emptyTitle}>What are you working on?</div>
    <div style={chatStyles.emptyDesc}>Ask about a paper in your library, your thesis argument, citations, or research methods.</div>
    <div style={chatStyles.suggestions}>
      {["Summarize the main argument", "Find methodological gaps", "Suggest related papers", "Draft a paragraph"].map(s => (
        <div key={s} style={chatStyles.suggestion}>{s}</div>
      ))}
    </div>
  </div>
);

const SendIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
);

const chatStyles = {
  root: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    overflow: 'hidden',
  },
  messages: {
    flex: 1,
    overflowY: 'auto',
    padding: '24px 0',
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
  },
  messageRow: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
    padding: '0 24px',
  },
  messageRowUser: { flexDirection: 'row-reverse' },
  assistantAvatar: {
    width: 28,
    height: 28,
    background: '#0d0d0d',
    borderRadius: 6,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    marginTop: 1,
  },
  assistantAvatarInner: {
    width: 14,
    height: 14,
    background: '#18E299',
    borderRadius: 3,
  },
  bubble: {
    maxWidth: '72%',
    padding: '12px 16px',
    borderRadius: 16,
    fontSize: 14,
    lineHeight: 1.65,
    color: '#0d0d0d',
  },
  bubbleUser: {
    background: '#0d0d0d',
    color: '#fff',
    borderRadius: '16px 4px 16px 16px',
  },
  bubbleAssistant: {
    background: '#fff',
    border: '1px solid rgba(0,0,0,0.06)',
    borderRadius: '4px 16px 16px 16px',
    boxShadow: 'rgba(0,0,0,0.03) 0px 2px 4px',
  },
  sources: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 10,
    paddingTop: 10,
    borderTop: '1px solid rgba(0,0,0,0.06)',
  },
  sourceTag: {
    fontSize: 11,
    fontWeight: 500,
    color: '#0fa76e',
    background: '#d4fae8',
    padding: '2px 8px',
    borderRadius: 9999,
  },
  composerWrap: {
    padding: '12px 24px 16px',
    borderTop: '1px solid rgba(0,0,0,0.05)',
    background: '#fff',
  },
  composer: {
    display: 'flex',
    alignItems: 'flex-end',
    gap: 8,
    border: '1px solid rgba(0,0,0,0.08)',
    borderRadius: 16,
    padding: '10px 10px 10px 16px',
    background: '#fff',
    boxShadow: 'rgba(0,0,0,0.03) 0px 2px 8px',
  },
  textarea: {
    flex: 1,
    border: 'none',
    outline: 'none',
    resize: 'none',
    fontFamily: "'Inter', sans-serif",
    fontSize: 14,
    lineHeight: 1.5,
    color: '#0d0d0d',
    background: 'transparent',
    padding: 0,
    maxHeight: 120,
    overflowY: 'auto',
  },
  sendBtn: {
    width: 32,
    height: 32,
    borderRadius: 9,
    border: 'none',
    background: '#e5e5e5',
    color: '#999',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'not-allowed',
    flexShrink: 0,
    transition: 'background 0.15s, color 0.15s',
  },
  sendBtnActive: {
    background: '#0d0d0d',
    color: '#fff',
    cursor: 'pointer',
  },
  hint: {
    fontSize: 11,
    color: '#bbb',
    marginTop: 6,
    paddingLeft: 4,
    fontFamily: "'Geist Mono', monospace",
    letterSpacing: '0.2px',
    textTransform: 'uppercase',
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    padding: '48px 32px',
    textAlign: 'center',
  },
  emptyIcon: {
    width: 44,
    height: 44,
    background: '#0d0d0d',
    borderRadius: 11,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  emptyIconMark: {
    width: 22,
    height: 22,
    background: '#18E299',
    borderRadius: 5,
  },
  emptyTitle: {
    fontSize: 17,
    fontWeight: 600,
    letterSpacing: '-0.2px',
    color: '#0d0d0d',
    marginBottom: 8,
  },
  emptyDesc: {
    fontSize: 14,
    color: '#666',
    lineHeight: 1.6,
    maxWidth: 320,
    marginBottom: 20,
  },
  suggestions: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8,
    justifyContent: 'center',
  },
  suggestion: {
    fontSize: 13,
    fontWeight: 500,
    color: '#333',
    background: '#fff',
    border: '1px solid rgba(0,0,0,0.08)',
    padding: '6px 14px',
    borderRadius: 9999,
    cursor: 'pointer',
  },
  dots: { display: 'flex', gap: 4, padding: '2px 0' },
  dot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: '#bbb',
    animation: 'bounce 1.2s infinite ease-in-out',
  },
};

Object.assign(window, { ChatThread });
