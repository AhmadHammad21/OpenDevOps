// Agent Logs — terminal-style log viewer

function AgentLogs() {
  const [selectedRun, setSelectedRun] = React.useState(0);
  const [filter, setFilter] = React.useState('all');

  const runs = [
    { id: 248, pipeline: 'deploy-api', agent: 'prod-agent-01', status: 'failed', time: '10:42 AM', duration: '18s' },
    { id: 247, pipeline: 'run-tests', agent: 'prod-agent-01', status: 'passed', time: '10:08 AM', duration: '42s' },
    { id: 246, pipeline: 'build-image', agent: 'staging-agent-02', status: 'passed', time: '9:51 AM', duration: '28s' },
    { id: 245, pipeline: 'deploy-worker', agent: 'prod-agent-01', status: 'passed', time: '9:12 AM', duration: '14s' },
    { id: 244, pipeline: 'deploy-api', agent: 'staging-agent-02', status: 'passed', time: 'Yesterday', duration: '22s' },
  ];

  const logsByRun = {
    0: [
      { ts: '10:42:01', level: 'INFO',  msg: 'Agent started — version v2.4.1' },
      { ts: '10:42:01', level: 'INFO',  msg: 'Connecting to cluster k8s-prod-01...' },
      { ts: '10:42:02', level: 'OK',    msg: 'Connected — 6 nodes healthy' },
      { ts: '10:42:03', level: 'INFO',  msg: 'Pulling image opendevops/api:v2.4.1' },
      { ts: '10:42:08', level: 'OK',    msg: 'Image pulled — sha256:a1b2c3d4e5f6' },
      { ts: '10:42:09', level: 'INFO',  msg: 'Deploying to namespace: production' },
      { ts: '10:42:11', level: 'WARN',  msg: 'Memory usage at 81% — threshold is 80%' },
      { ts: '10:42:14', level: 'ERROR', msg: 'Health check failed: pod web-7f9b4 not ready (timeout: 30s)' },
      { ts: '10:42:14', level: 'INFO',  msg: 'Initiating rollback to v2.3.0...' },
      { ts: '10:42:19', level: 'OK',    msg: 'Rollback complete — serving v2.3.0' },
      { ts: '10:42:19', level: 'DEBUG', msg: 'Run duration: 18.4s · exit code: 1' },
    ],
    1: [
      { ts: '10:08:01', level: 'INFO',  msg: 'Starting test suite — 142 tests' },
      { ts: '10:08:04', level: 'OK',    msg: 'Unit tests passed (98/98)' },
      { ts: '10:08:28', level: 'WARN',  msg: 'Integration test slow (14.2s) — auth service' },
      { ts: '10:08:42', level: 'OK',    msg: 'All 142 tests passed in 41.8s' },
    ],
  };

  const levelColors = { INFO: '#79C0FF', OK: '#3FB950', WARN: '#E3B341', ERROR: '#FF7B72', DEBUG: '#6B7280' };
  const levelLabels = { INFO: 'INFO ', OK: '  OK ', WARN: 'WARN ', ERROR: 'ERROR', DEBUG: 'DEBUG' };

  const logs = logsByRun[selectedRun] || logsByRun[0];
  const filteredLogs = filter === 'all' ? logs : logs.filter(l => l.level === filter.toUpperCase() || (filter === 'ok' && l.level === 'OK'));

  const s = {
    page: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#F9FAFB' },
    header: { background: '#fff', borderBottom: '1px solid #E5E7EB', padding: '16px 28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 },
    body: { flex: 1, display: 'flex', overflow: 'hidden' },
    runList: { width: 260, borderRight: '1px solid #E5E7EB', background: '#fff', display: 'flex', flexDirection: 'column', flexShrink: 0, overflow: 'auto' },
    runItem: (active) => ({ padding: '11px 16px', cursor: 'pointer', borderBottom: '1px solid #F3F4F6', background: active ? '#F9FAFB' : 'transparent', borderLeft: active ? '2px solid #6366F1' : '2px solid transparent', transition: 'background 100ms' }),
    termPanel: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#0D1117' },
    termHeader: { background: '#21262D', borderBottom: '1px solid #30363D', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 },
    termBody: { flex: 1, overflow: 'auto', padding: '14px 18px', fontFamily: 'var(--font-mono)' },
    filterBtn: (active) => ({ background: active ? '#1C2128' : 'transparent', color: active ? '#E6EDF3' : '#8B949E', border: `1px solid ${active ? '#30363D' : 'transparent'}`, borderRadius: 4, fontSize: 11, fontWeight: 500, padding: '3px 8px', cursor: 'pointer', fontFamily: 'var(--font-mono)', transition: 'all 100ms' }),
  };

  const statusBadge = (status) => {
    if (status === 'passed') return <Badge variant="green" dot>Passed</Badge>;
    if (status === 'failed') return <Badge variant="red" dot>Failed</Badge>;
    return <Badge variant="default" dot>{status}</Badge>;
  };

  return (
    <div style={s.page}>
      <div style={s.header}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#111827' }}>Agent logs</div>
          <div style={{ fontSize: 13, color: '#6B7280', marginTop: 1 }}>Real-time output from agent runs</div>
        </div>
        <Btn variant="secondary" size="sm" icon="refresh">Refresh</Btn>
      </div>

      <div style={s.body}>
        {/* Run list */}
        <div style={s.runList}>
          <div style={{ padding: '10px 12px', borderBottom: '1px solid #F3F4F6' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#F3F4F6', borderRadius: 6, padding: '6px 10px' }}>
              <Icon name="search" size={13} color="#9CA3AF" />
              <input placeholder="Filter runs..." style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: 12, color: '#374151', fontFamily: 'var(--font-sans)', flex: 1 }} />
            </div>
          </div>
          {runs.map((r, i) => (
            <div key={i} style={s.runItem(selectedRun === i)} onClick={() => setSelectedRun(i)}
              onMouseEnter={e => { if (selectedRun !== i) e.currentTarget.style.background = '#F9FAFB'; }}
              onMouseLeave={e => { if (selectedRun !== i) e.currentTarget.style.background = 'transparent'; }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 500, color: '#374151' }}>{r.pipeline}</span>
                {statusBadge(r.status)}
              </div>
              <div style={{ fontSize: 11, color: '#9CA3AF', display: 'flex', gap: 8 }}>
                <span>#{r.id}</span>
                <span>{r.agent}</span>
                <span style={{ marginLeft: 'auto' }}>{r.time}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Terminal */}
        <div style={s.termPanel}>
          <div style={s.termHeader}>
            <div style={{ display: 'flex', gap: 6 }}>
              <div style={{ width: 11, height: 11, borderRadius: '50%', background: '#FF5F57' }}></div>
              <div style={{ width: 11, height: 11, borderRadius: '50%', background: '#FEBC2E' }}></div>
              <div style={{ width: 11, height: 11, borderRadius: '50%', background: '#28C840' }}></div>
            </div>
            <span style={{ fontSize: 12, color: '#8B949E', fontFamily: 'var(--font-sans)', flex: 1, marginLeft: 8 }}>
              {runs[selectedRun].pipeline} · {runs[selectedRun].agent} · run #{runs[selectedRun].id}
            </span>
            <div style={{ display: 'flex', gap: 4 }}>
              {['all', 'error', 'warn', 'ok'].map(f => (
                <button key={f} style={s.filterBtn(filter === f)} onClick={() => setFilter(f)}>{f}</button>
              ))}
            </div>
            <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#8B949E', marginLeft: 8, padding: 2 }}>
              <Icon name="copy" size={13} color="#8B949E" />
            </button>
          </div>
          <div style={s.termBody}>
            {filteredLogs.map((log, i) => (
              <div key={i} style={{ fontSize: 12, lineHeight: 1.8, display: 'flex', gap: 12 }}>
                <span style={{ color: '#6B7280', userSelect: 'none', flexShrink: 0 }}>{log.ts}</span>
                <span style={{ color: levelColors[log.level], flexShrink: 0, fontWeight: log.level === 'ERROR' ? 600 : 400 }}>[{levelLabels[log.level]}]</span>
                <span style={{ color: log.level === 'ERROR' ? '#FF7B72' : log.level === 'WARN' ? '#E3B341' : '#E6EDF3' }}>{log.msg}</span>
              </div>
            ))}
            <div style={{ fontSize: 12, lineHeight: 1.8, color: '#8B949E', display: 'flex', gap: 4, marginTop: 4 }}>
              <span>$</span>
              <span style={{ width: 7, height: 14, background: '#6366F1', display: 'inline-block', verticalAlign: 'middle', animation: 'blink 1.1s step-end infinite' }}></span>
            </div>
          </div>
        </div>
      </div>
      <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
    </div>
  );
}

Object.assign(window, { AgentLogs });
