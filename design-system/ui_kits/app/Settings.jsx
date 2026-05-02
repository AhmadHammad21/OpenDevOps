// Settings screen — env variables, integrations, agent config

function Settings() {
  const [activeTab, setActiveTab] = React.useState('env');
  const [envVars, setEnvVars] = React.useState([
    { key: 'API_KEY', value: 'sk-prod-abcdef123456', masked: true, isSecret: true },
    { key: 'DB_HOST', value: 'postgres://prod.cluster.internal', masked: false, isSecret: false },
    { key: 'REDIS_URL', value: 'redis://cache.internal:6379', masked: false, isSecret: false },
    { key: 'WEBHOOK_SECRET', value: 'wh-secret-xyz789', masked: true, isSecret: true },
  ]);
  const [showValues, setShowValues] = React.useState({});
  const [newKey, setNewKey] = React.useState('');
  const [newVal, setNewVal] = React.useState('');
  const [saved, setSaved] = React.useState(false);

  function toggleShow(key) {
    setShowValues(prev => ({ ...prev, [key]: !prev[key] }));
  }

  function addVar() {
    if (!newKey.trim()) return;
    setEnvVars(prev => [...prev, { key: newKey.toUpperCase(), value: newVal, masked: false, isSecret: false }]);
    setNewKey(''); setNewVal('');
  }

  function removeVar(key) {
    setEnvVars(prev => prev.filter(v => v.key !== key));
  }

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  const tabs = [
    { id: 'env', label: 'Environment' },
    { id: 'agent', label: 'Agent config' },
    { id: 'integrations', label: 'Integrations' },
    { id: 'notifications', label: 'Notifications' },
  ];

  const s = {
    page: { flex: 1, overflow: 'auto', background: '#F9FAFB' },
    header: { background: '#fff', borderBottom: '1px solid #E5E7EB', padding: '16px 28px' },
    content: { padding: '24px 28px', maxWidth: 780 },
    card: { background: '#fff', border: '1px solid #E5E7EB', borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 2px rgba(0,0,0,0.04)', marginBottom: 16 },
    cardHeader: { padding: '14px 18px', borderBottom: '1px solid #F3F4F6', display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
    cardTitle: { fontSize: 13, fontWeight: 600, color: '#111827' },
    cardSub: { fontSize: 12, color: '#6B7280', marginTop: 2 },
    row: { display: 'flex', alignItems: 'center', gap: 8, padding: '9px 18px', borderBottom: '1px solid #F9FAFB' },
    input: { fontFamily: 'var(--font-mono)', fontSize: 12, color: '#111827', background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: 5, padding: '5px 8px', outline: 'none' },
    tabRow: { display: 'flex', gap: 0, borderBottom: '1px solid #E5E7EB', background: '#fff', padding: '0 28px' },
    tab: (active) => ({ padding: '10px 16px', fontSize: 13, fontWeight: 500, color: active ? '#4F46E5' : '#6B7280', borderBottom: active ? '2px solid #6366F1' : '2px solid transparent', cursor: 'pointer', transition: 'color 120ms', marginBottom: -1, background: 'none', border: 'none', fontFamily: 'inherit' }),
  };

  return (
    <div style={s.page}>
      <div style={s.header}>
        <div style={{ fontSize: 16, fontWeight: 600, color: '#111827' }}>Settings</div>
        <div style={{ fontSize: 13, color: '#6B7280', marginTop: 1 }}>Manage your agent configuration and environment</div>
      </div>

      <div style={s.tabRow}>
        {tabs.map(t => (
          <button key={t.id} style={s.tab(activeTab === t.id)} onClick={() => setActiveTab(t.id)}>{t.label}</button>
        ))}
      </div>

      <div style={s.content}>
        {activeTab === 'env' && (
          <>
            <div style={s.card}>
              <div style={s.cardHeader}>
                <div>
                  <div style={s.cardTitle}>Environment variables</div>
                  <div style={s.cardSub}>Available to all agents in this workspace</div>
                </div>
                <Btn variant="secondary" size="sm" icon="plus" onClick={() => {}}>Add variable</Btn>
              </div>
              {/* Table header */}
              <div style={{ display: 'flex', gap: 0, padding: '7px 18px', background: '#F9FAFB', borderBottom: '1px solid #E5E7EB' }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#9CA3AF', letterSpacing: '0.07em', textTransform: 'uppercase', flex: '0 0 180px' }}>Key</span>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#9CA3AF', letterSpacing: '0.07em', textTransform: 'uppercase', flex: 1 }}>Value</span>
                <span style={{ width: 60 }}></span>
              </div>
              {envVars.map((v, i) => (
                <div key={v.key} style={{ ...s.row, borderBottom: i < envVars.length - 1 ? '1px solid #F3F4F6' : 'none' }}>
                  <div style={{ flex: '0 0 180px', display: 'flex', alignItems: 'center', gap: 6 }}>
                    {v.isSecret && <Icon name="key" size={12} color="#9CA3AF" />}
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 500, color: '#374151' }}>{v.key}</span>
                  </div>
                  <div style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: 12, color: '#6B7280', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {v.isSecret && !showValues[v.key] ? '••••••••••••' : v.value}
                  </div>
                  <div style={{ display: 'flex', gap: 2, width: 60, justifyContent: 'flex-end' }}>
                    {v.isSecret && (
                      <button onClick={() => toggleShow(v.key)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: '#9CA3AF', borderRadius: 4 }}>
                        <Icon name={showValues[v.key] ? 'eyeOff' : 'eye'} size={13} />
                      </button>
                    )}
                    <button onClick={() => removeVar(v.key)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: '#9CA3AF', borderRadius: 4 }}>
                      <Icon name="trash" size={13} />
                    </button>
                  </div>
                </div>
              ))}
              {/* Add row */}
              <div style={{ display: 'flex', gap: 8, padding: '10px 18px', borderTop: '1px solid #F3F4F6', alignItems: 'center' }}>
                <input value={newKey} onChange={e => setNewKey(e.target.value)} placeholder="NEW_KEY" style={{ ...s.input, flex: '0 0 172px' }} />
                <input value={newVal} onChange={e => setNewVal(e.target.value)} placeholder="value" style={{ ...s.input, flex: 1 }} onKeyDown={e => e.key === 'Enter' && addVar()} />
                <Btn variant="secondary" size="sm" onClick={addVar}>Add</Btn>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <Btn variant="ghost" size="sm">Discard changes</Btn>
              <Btn variant="primary" size="sm" onClick={handleSave} icon={saved ? 'check' : undefined}>
                {saved ? 'Saved!' : 'Save changes'}
              </Btn>
            </div>
          </>
        )}

        {activeTab === 'agent' && (
          <div style={s.card}>
            <div style={s.cardHeader}><div style={s.cardTitle}>Agent configuration</div></div>
            <div style={{ padding: '18px' }}>
              {[
                { label: 'Agent name', value: 'prod-agent-01', hint: 'Used as the agent identifier in logs' },
                { label: 'Default region', value: 'us-east-1', hint: 'AWS region for deployments' },
                { label: 'Cluster', value: 'k8s-prod', hint: 'Target Kubernetes cluster' },
                { label: 'Namespace', value: 'production', hint: 'Kubernetes namespace' },
              ].map((f, i) => (
                <div key={i} style={{ marginBottom: 16 }}>
                  <label style={{ fontSize: 12, fontWeight: 500, color: '#374151', display: 'block', marginBottom: 5 }}>{f.label}</label>
                  <input defaultValue={f.value} style={{ ...s.input, background: '#fff', border: '1px solid #D1D5DB', borderRadius: 6, padding: '7px 10px', width: '100%', fontFamily: 'var(--font-sans)', fontSize: 13, boxSizing: 'border-box' }} />
                  <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>{f.hint}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'integrations' && (
          <div style={s.card}>
            <div style={s.cardHeader}><div style={s.cardTitle}>Integrations</div></div>
            {[
              { name: 'GitHub', desc: 'Connect your repositories', connected: true },
              { name: 'Slack', desc: 'Get deployment notifications', connected: false },
              { name: 'PagerDuty', desc: 'Alert on failures', connected: false },
              { name: 'Datadog', desc: 'Send metrics and traces', connected: true },
            ].map((intg, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 18px', borderBottom: i < 3 ? '1px solid #F3F4F6' : 'none' }}>
                <div style={{ width: 34, height: 34, background: '#F3F4F6', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Icon name="git" size={16} color="#6B7280" />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: '#111827' }}>{intg.name}</div>
                  <div style={{ fontSize: 12, color: '#6B7280' }}>{intg.desc}</div>
                </div>
                {intg.connected
                  ? <Badge variant="green" dot>Connected</Badge>
                  : <Btn variant="secondary" size="sm">Connect</Btn>
                }
              </div>
            ))}
          </div>
        )}

        {activeTab === 'notifications' && (
          <div style={{ ...s.card, padding: 18 }}>
            <div style={{ fontSize: 13, color: '#6B7280' }}>Notification preferences coming soon.</div>
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { Settings });
