// Chat interface — Claude-style with sidebar conversations

function ChatInterface() {
  const [conversations, setConversations] = React.useState([
    { id: 1, title: 'Deploy to production', time: '12m ago', active: true },
    { id: 2, title: 'Debug failing health check', time: '1h ago', active: false },
    { id: 3, title: 'Scale k8s deployment', time: 'Yesterday', active: false },
    { id: 4, title: 'Set up staging env vars', time: 'Yesterday', active: false },
    { id: 5, title: 'Rollback prod-agent-01', time: '3d ago', active: false },
  ]);

  const [activeConv, setActiveConv] = React.useState(1);
  const [input, setInput] = React.useState('');
  const [messages, setMessages] = React.useState([
    { role: 'assistant', content: "Hi Jane! I'm your DevOps agent. I can deploy services, check pipeline status, manage environment variables, scale infrastructure, and more. What would you like to do?", time: '10:30 AM' },
    { role: 'user', content: 'Deploy the API service to production', time: '10:31 AM' },
    { role: 'assistant', content: null, isCommand: true, time: '10:31 AM', steps: [
      { status: 'ok', text: 'Connected to k8s-prod-01 (6 nodes healthy)' },
      { status: 'ok', text: 'Pulling image opendevops/api:v2.4.1' },
      { status: 'ok', text: 'Image pulled — sha256:a1b2c3d4' },
      { status: 'warn', text: 'Memory at 81% — consider scaling' },
      { status: 'err', text: 'Health check failed: pod web-7f9b4' },
      { status: 'info', text: 'Rolling back to v2.3.0...' },
      { status: 'ok', text: 'Rollback complete — serving v2.3.0' },
    ], summary: 'Deployment failed — health check on web-7f9b4 was not ready. I\'ve rolled back to v2.3.0. Would you like me to investigate the failing pod, or try redeploying with a lower replica count?' },
    { role: 'user', content: 'Investigate the failing pod', time: '10:32 AM' },
    { role: 'assistant', content: "I checked `web-7f9b4`. It's running out of memory — current limit is 512Mi but the process needs ~620Mi. I recommend bumping the memory limit to 768Mi in your deployment config.\n\nShould I apply that change and retry the deployment?", time: '10:32 AM' },
  ]);

  const [thinking, setThinking] = React.useState(false);

  function sendMessage() {
    if (!input.trim()) return;
    const newMsg = { role: 'user', content: input, time: 'Just now' };
    setMessages(prev => [...prev, newMsg]);
    setInput('');
    setThinking(true);
    setTimeout(() => {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: "I'm on it. Updating the memory limit for `web-7f9b4` to 768Mi and retrying the deployment...",
        time: 'Just now',
      }]);
      setThinking(false);
    }, 1400);
  }

  const statusColors = { ok: '#3FB950', warn: '#E3B341', err: '#FF7B72', info: '#79C0FF' };
  const statusLabels = { ok: '✓', warn: '⚠', err: '✗', info: '→' };

  const chatStyles = {
    container: { flex: 1, display: 'flex', overflow: 'hidden', background: '#fff' },
    convSidebar: { width: 228, borderRight: '1px solid #E5E7EB', display: 'flex', flexDirection: 'column', background: '#F9FAFB', flexShrink: 0 },
    convHeader: { padding: '14px 14px 10px', borderBottom: '1px solid #E5E7EB', display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
    convTitle: { fontSize: 12, fontWeight: 600, color: '#374151' },
    convItem: (active) => ({
      padding: '9px 12px', cursor: 'pointer', borderBottom: '1px solid transparent',
      background: active ? '#fff' : 'transparent',
      borderLeft: active ? '2px solid #6366F1' : '2px solid transparent',
      transition: 'background 100ms',
    }),
    convName: (active) => ({ fontSize: 13, fontWeight: active ? 500 : 400, color: active ? '#111827' : '#6B7280', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }),
    convTime: { fontSize: 11, color: '#9CA3AF', marginTop: 2 },
    mainChat: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' },
    chatHeader: { padding: '12px 20px', borderBottom: '1px solid #F3F4F6', display: 'flex', alignItems: 'center', gap: 10 },
    messages: { flex: 1, overflow: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: 20 },
    inputArea: { padding: '12px 20px', borderTop: '1px solid #E5E7EB' },
    inputWrap: { border: '1px solid #D1D5DB', borderRadius: 10, padding: '10px 12px', display: 'flex', alignItems: 'flex-end', gap: 8, background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,0.04)', transition: 'border-color 150ms, box-shadow 150ms' },
  };

  return (
    <div style={chatStyles.container}>
      {/* Conversations sidebar */}
      <div style={chatStyles.convSidebar}>
        <div style={chatStyles.convHeader}>
          <span style={chatStyles.convTitle}>Conversations</span>
          <button onClick={() => {}} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, color: '#6366F1' }}>
            <Icon name="plus" size={16} />
          </button>
        </div>
        <div style={{ flex: 1, overflow: 'auto', paddingTop: 4 }}>
          {conversations.map(c => (
            <div key={c.id} style={chatStyles.convItem(c.id === activeConv)}
              onClick={() => setActiveConv(c.id)}
              onMouseEnter={e => { if (c.id !== activeConv) e.currentTarget.style.background = '#F3F4F6'; }}
              onMouseLeave={e => { if (c.id !== activeConv) e.currentTarget.style.background = 'transparent'; }}
            >
              <div style={chatStyles.convName(c.id === activeConv)}>{c.title}</div>
              <div style={chatStyles.convTime}>{c.time}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Main chat */}
      <div style={chatStyles.mainChat}>
        <div style={chatStyles.chatHeader}>
          <div style={{ width: 30, height: 30, background: '#EEF2FF', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="bot" size={16} color="#6366F1" />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>DevOps Agent</div>
            <div style={{ fontSize: 11, color: '#10B981', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10B981', display: 'inline-block' }}></span>
              Active · prod-agent-01
            </div>
          </div>
        </div>

        <div style={chatStyles.messages}>
          {messages.map((msg, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, flexDirection: msg.role === 'user' ? 'row-reverse' : 'row', alignItems: 'flex-start' }}>
              {msg.role === 'assistant'
                ? <div style={{ width: 28, height: 28, background: '#EEF2FF', borderRadius: 7, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Icon name="bot" size={14} color="#6366F1" /></div>
                : <Avatar name="Jane Doe" size={28} />
              }
              <div style={{ maxWidth: '72%', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {msg.isCommand ? (
                  <div style={{ background: '#0D1117', borderRadius: 8, border: '1px solid #30363D', overflow: 'hidden' }}>
                    <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                      {msg.steps.map((step, j) => (
                        <div key={j} style={{ fontSize: 12, fontFamily: 'var(--font-mono)', lineHeight: 1.7, color: statusColors[step.status] }}>
                          {statusLabels[step.status]} {step.text}
                        </div>
                      ))}
                    </div>
                    <div style={{ borderTop: '1px solid #30363D', padding: '10px 12px', fontSize: 13, color: '#E6EDF3', lineHeight: 1.6 }}>{msg.summary}</div>
                  </div>
                ) : (
                  <div style={{
                    padding: '10px 14px', borderRadius: msg.role === 'user' ? '10px 2px 10px 10px' : '2px 10px 10px 10px',
                    background: msg.role === 'user' ? '#6366F1' : '#F9FAFB',
                    border: msg.role === 'user' ? 'none' : '1px solid #E5E7EB',
                    fontSize: 13, lineHeight: 1.65,
                    color: msg.role === 'user' ? '#fff' : '#374151',
                    whiteSpace: 'pre-wrap',
                  }}>
                    {msg.content}
                  </div>
                )}
                <div style={{ fontSize: 11, color: '#9CA3AF', textAlign: msg.role === 'user' ? 'right' : 'left' }}>{msg.time}</div>
              </div>
            </div>
          ))}
          {thinking && (
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <div style={{ width: 28, height: 28, background: '#EEF2FF', borderRadius: 7, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Icon name="bot" size={14} color="#6366F1" /></div>
              <div style={{ padding: '10px 14px', background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: '2px 10px 10px 10px', display: 'flex', gap: 4, alignItems: 'center' }}>
                {[0,1,2].map(d => <span key={d} style={{ width: 6, height: 6, borderRadius: '50%', background: '#9CA3AF', display: 'inline-block', animation: `bounce 1.2s ${d*0.2}s infinite` }}></span>)}
              </div>
            </div>
          )}
        </div>

        <div style={chatStyles.inputArea}>
          <div style={chatStyles.inputWrap} onFocus={e => { e.currentTarget.style.borderColor='#6366F1'; e.currentTarget.style.boxShadow='0 0 0 3px rgba(99,102,241,0.12)'; }} onBlur={e => { e.currentTarget.style.borderColor='#D1D5DB'; e.currentTarget.style.boxShadow='0 1px 2px rgba(0,0,0,0.04)'; }}>
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
              placeholder="Ask your agent anything — deploy, scale, debug, monitor…"
              rows={1}
              style={{ flex: 1, border: 'none', outline: 'none', resize: 'none', fontFamily: 'var(--font-sans)', fontSize: 13, color: '#111827', background: 'transparent', lineHeight: 1.5, maxHeight: 120, overflowY: 'auto' }}
            />
            <button onClick={sendMessage} style={{ background: input.trim() ? '#6366F1' : '#E5E7EB', border: 'none', borderRadius: 7, width: 30, height: 30, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: input.trim() ? 'pointer' : 'default', transition: 'background 120ms', flexShrink: 0 }}>
              <Icon name="send" size={13} color={input.trim() ? '#fff' : '#9CA3AF'} />
            </button>
          </div>
          <div style={{ fontSize: 11, color: '#9CA3AF', textAlign: 'center', marginTop: 8 }}>Press Enter to send · Shift+Enter for new line</div>
        </div>
      </div>

      <style>{`@keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-6px)} }`}</style>
    </div>
  );
}

Object.assign(window, { ChatInterface });
