// Dashboard screen component

function Dashboard({ onNavigate }) {
  const stats = [
    { label: 'Active agents', value: '3', sub: '2 healthy, 1 degraded', color: '#111827' },
    { label: 'Pipelines today', value: '48', sub: '46 passed · 2 failed', color: '#111827' },
    { label: 'Avg deploy time', value: '4.2s', sub: 'Down 12% from last week', color: '#059669' },
    { label: 'Uptime (30d)', value: '99.8%', sub: 'SLA target: 99.5%', color: '#059669' },
  ];

  const agents = [
    { name: 'prod-agent-01', region: 'us-east-1', cluster: 'k8s-prod', status: 'healthy', version: 'v2.4.1', lastRun: '12m ago' },
    { name: 'staging-agent-02', region: 'eu-west-1', cluster: 'k8s-staging', status: 'degraded', version: 'v2.3.0', lastRun: '3h ago' },
    { name: 'dev-agent-03', region: 'us-west-2', cluster: 'k8s-dev', status: 'healthy', version: 'v2.4.1', lastRun: '28m ago' },
  ];

  const recentRuns = [
    { pipeline: 'deploy-api', branch: 'main', status: 'passed', duration: '18s', time: '12m ago' },
    { pipeline: 'run-tests', branch: 'feat/auth', status: 'passed', duration: '42s', time: '34m ago' },
    { pipeline: 'deploy-worker', branch: 'main', status: 'failed', duration: '11s', time: '1h ago' },
    { pipeline: 'build-image', branch: 'main', status: 'passed', duration: '28s', time: '2h ago' },
  ];

  const statusConfig = {
    healthy:  { variant: 'green', label: 'Healthy' },
    degraded: { variant: 'amber', label: 'Degraded' },
    failed:   { variant: 'red',   label: 'Failed' },
    passed:   { variant: 'green', label: 'Passed' },
  };

  const dashStyles = {
    page: { flex: 1, overflow: 'auto', background: '#F9FAFB', display: 'flex', flexDirection: 'column' },
    header: { background: '#fff', borderBottom: '1px solid #E5E7EB', padding: '16px 28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
    content: { padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 24 },
    sectionTitle: { fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 12 },
    statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 },
    statCard: { background: '#fff', border: '1px solid #E5E7EB', borderRadius: 8, padding: '16px 18px', boxShadow: '0 1px 2px rgba(0,0,0,0.04)' },
    agentsGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 },
    agentCard: { background: '#fff', border: '1px solid #E5E7EB', borderRadius: 8, padding: 16, boxShadow: '0 1px 2px rgba(0,0,0,0.04)' },
    table: { background: '#fff', border: '1px solid #E5E7EB', borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 2px rgba(0,0,0,0.04)' },
    th: { fontSize: 11, fontWeight: 600, color: '#9CA3AF', letterSpacing: '0.06em', textTransform: 'uppercase', padding: '10px 16px', textAlign: 'left', background: '#F9FAFB', borderBottom: '1px solid #E5E7EB' },
    td: { fontSize: 13, color: '#374151', padding: '11px 16px', borderBottom: '1px solid #F3F4F6', verticalAlign: 'middle' },
  };

  return (
    <div style={dashStyles.page}>
      <div style={dashStyles.header}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#111827' }}>Dashboard</div>
          <div style={{ fontSize: 13, color: '#6B7280', marginTop: 1 }}>Good morning, Jane. 3 agents are active.</div>
        </div>
        <Btn variant="primary" icon="play" size="sm" onClick={() => onNavigate('chat')}>Ask agent</Btn>
      </div>

      <div style={dashStyles.content}>
        {/* Stats */}
        <div>
          <div style={dashStyles.statsGrid}>
            {stats.map((s, i) => (
              <div key={i} style={dashStyles.statCard}>
                <div style={{ fontSize: 28, fontWeight: 700, color: s.color, letterSpacing: '-0.03em', lineHeight: 1.1 }}>{s.value}</div>
                <div style={{ fontSize: 13, fontWeight: 500, color: '#111827', marginTop: 4 }}>{s.label}</div>
                <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>{s.sub}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Agents */}
        <div>
          <div style={dashStyles.sectionTitle}>Agents</div>
          <div style={dashStyles.agentsGrid}>
            {agents.map((a, i) => (
              <div key={i} style={dashStyles.agentCard}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>{a.name}</div>
                    <div style={{ fontSize: 12, color: '#6B7280', marginTop: 1 }}>{a.region} · {a.cluster}</div>
                  </div>
                  <Badge variant={statusConfig[a.status].variant} dot>{statusConfig[a.status].label}</Badge>
                </div>
                <div style={{ borderTop: '1px solid #F3F4F6', paddingTop: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 12, color: '#6B7280' }}>Last run</span>
                    <span style={{ fontSize: 12, color: '#374151', fontFamily: 'var(--font-mono)' }}>{a.lastRun}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 12, color: '#6B7280' }}>Version</span>
                    <span style={{ fontSize: 12, color: '#374151', fontFamily: 'var(--font-mono)' }}>{a.version}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent runs */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <div style={dashStyles.sectionTitle}>Recent pipeline runs</div>
            <button onClick={() => onNavigate('pipelines')} style={{ background: 'none', border: 'none', fontSize: 12, color: '#6366F1', cursor: 'pointer', fontFamily: 'inherit', fontWeight: 500 }}>View all</button>
          </div>
          <div style={dashStyles.table}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={dashStyles.th}>Pipeline</th>
                  <th style={dashStyles.th}>Branch</th>
                  <th style={dashStyles.th}>Status</th>
                  <th style={dashStyles.th}>Duration</th>
                  <th style={dashStyles.th}>Time</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((r, i) => (
                  <tr key={i} style={{ cursor: 'pointer' }} onMouseEnter={e => e.currentTarget.style.background='#F9FAFB'} onMouseLeave={e => e.currentTarget.style.background='transparent'}>
                    <td style={dashStyles.td}><span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{r.pipeline}</span></td>
                    <td style={dashStyles.td}><span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#6B7280' }}>{r.branch}</span></td>
                    <td style={dashStyles.td}><Badge variant={r.status === 'passed' ? 'green' : 'red'} dot>{r.status}</Badge></td>
                    <td style={dashStyles.td}><span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{r.duration}</span></td>
                    <td style={{ ...dashStyles.td, color: '#9CA3AF', borderBottom: i === recentRuns.length - 1 ? 'none' : '1px solid #F3F4F6' }}>{r.time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Dashboard });
