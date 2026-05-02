// Pipelines screen — workflow visualization

function Pipelines() {
  const [selected, setSelected] = React.useState(null);

  const pipelines = [
    {
      name: 'deploy-api', branch: 'main', status: 'failed', lastRun: '12m ago', duration: '18s',
      steps: [
        { name: 'checkout', status: 'passed', duration: '1s' },
        { name: 'build-image', status: 'passed', duration: '8s' },
        { name: 'push-image', status: 'passed', duration: '3s' },
        { name: 'deploy', status: 'failed', duration: '5s' },
        { name: 'health-check', status: 'skipped', duration: '—' },
      ]
    },
    {
      name: 'run-tests', branch: 'feat/auth', status: 'passed', lastRun: '34m ago', duration: '42s',
      steps: [
        { name: 'checkout', status: 'passed', duration: '1s' },
        { name: 'install-deps', status: 'passed', duration: '12s' },
        { name: 'unit-tests', status: 'passed', duration: '18s' },
        { name: 'integration-tests', status: 'passed', duration: '11s' },
      ]
    },
    {
      name: 'build-image', branch: 'main', status: 'passed', lastRun: '1h ago', duration: '28s',
      steps: [
        { name: 'checkout', status: 'passed', duration: '1s' },
        { name: 'lint', status: 'passed', duration: '4s' },
        { name: 'build', status: 'passed', duration: '18s' },
        { name: 'push', status: 'passed', duration: '5s' },
      ]
    },
    {
      name: 'deploy-worker', branch: 'main', status: 'running', lastRun: 'now', duration: '7s…',
      steps: [
        { name: 'checkout', status: 'passed', duration: '1s' },
        { name: 'build-image', status: 'passed', duration: '4s' },
        { name: 'deploy', status: 'running', duration: '2s…' },
        { name: 'health-check', status: 'pending', duration: '—' },
      ]
    },
  ];

  const statusConfig = {
    passed:  { color: '#10B981', bg: '#ECFDF5', border: '#A7F3D0', label: 'Passed', icon: '✓' },
    failed:  { color: '#E11D48', bg: '#FFF1F2', border: '#FECDD3', label: 'Failed', icon: '✗' },
    running: { color: '#6366F1', bg: '#EEF2FF', border: '#C7D2FE', label: 'Running', icon: '●' },
    skipped: { color: '#9CA3AF', bg: '#F3F4F6', border: '#E5E7EB', label: 'Skipped', icon: '—' },
    pending: { color: '#9CA3AF', bg: '#F9FAFB', border: '#E5E7EB', label: 'Pending', icon: '○' },
  };

  const s = {
    page: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#F9FAFB' },
    header: { background: '#fff', borderBottom: '1px solid #E5E7EB', padding: '16px 28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 },
    body: { flex: 1, overflow: 'auto', padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 10 },
    card: (active) => ({ background: '#fff', border: `1px solid ${active ? '#C7D2FE' : '#E5E7EB'}`, borderRadius: 8, overflow: 'hidden', boxShadow: active ? '0 0 0 3px rgba(99,102,241,0.1)' : '0 1px 2px rgba(0,0,0,0.04)', cursor: 'pointer', transition: 'all 150ms' }),
    cardHeader: { padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 12 },
    steps: { padding: '12px 18px 14px', borderTop: '1px solid #F3F4F6', display: 'flex', gap: 0, alignItems: 'center' },
  };

  function StepNode({ step, isLast }) {
    const cfg = statusConfig[step.status];
    return (
      <div style={{ display: 'flex', alignItems: 'center', flex: isLast ? '0 0 auto' : 1 }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}>
          <div style={{ width: 28, height: 28, borderRadius: '50%', background: cfg.bg, border: `1.5px solid ${cfg.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: cfg.color, fontWeight: 600, position: 'relative' }}>
            {step.status === 'running'
              ? <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#6366F1', animation: 'pulse 1.5s infinite' }}></span>
              : step.icon || cfg.icon
            }
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 10, fontWeight: 500, color: '#374151', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>{step.name}</div>
            <div style={{ fontSize: 10, color: '#9CA3AF', fontFamily: 'var(--font-mono)' }}>{step.duration}</div>
          </div>
        </div>
        {!isLast && <div style={{ flex: 1, height: 1.5, background: step.status === 'pending' || step.status === 'skipped' ? '#E5E7EB' : cfg.color, margin: '0 6px', marginTop: -24, opacity: 0.5 }}></div>}
      </div>
    );
  }

  return (
    <div style={s.page}>
      <div style={s.header}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#111827' }}>Pipelines</div>
          <div style={{ fontSize: 13, color: '#6B7280', marginTop: 1 }}>4 pipelines · 1 running · 1 failed</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn variant="secondary" size="sm" icon="refresh">Refresh</Btn>
          <Btn variant="primary" size="sm" icon="play">Run pipeline</Btn>
        </div>
      </div>

      <div style={s.body}>
        {pipelines.map((p, i) => {
          const cfg = statusConfig[p.status];
          const isSelected = selected === i;
          return (
            <div key={i} style={s.card(isSelected)} onClick={() => setSelected(isSelected ? null : i)}>
              <div style={s.cardHeader}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: cfg.color, flexShrink: 0, animation: p.status === 'running' ? 'pulse 1.5s infinite' : 'none' }}></div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: '#111827' }}>{p.name}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#9CA3AF' }}>{p.branch}</span>
                  </div>
                </div>
                <Badge variant={p.status === 'passed' ? 'green' : p.status === 'failed' ? 'red' : p.status === 'running' ? 'blue' : 'default'} dot>{cfg.label}</Badge>
                <span style={{ fontSize: 12, color: '#9CA3AF', fontFamily: 'var(--font-mono)', marginLeft: 4 }}>{p.duration}</span>
                <span style={{ fontSize: 12, color: '#9CA3AF', marginLeft: 8 }}>{p.lastRun}</span>
                <Icon name={isSelected ? 'chevronDown' : 'chevronRight'} size={14} color="#9CA3AF" />
              </div>

              {isSelected && (
                <div style={s.steps}>
                  {p.steps.map((step, j) => (
                    <StepNode key={j} step={step} isLast={j === p.steps.length - 1} />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
      `}</style>
    </div>
  );
}

Object.assign(window, { Pipelines });
