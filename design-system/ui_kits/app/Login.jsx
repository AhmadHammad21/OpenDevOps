// Login / onboarding screen

function Login({ onLogin }) {
  const [step, setStep] = React.useState('login'); // 'login' | 'onboard'
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [showPass, setShowPass] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [orgName, setOrgName] = React.useState('');
  const [agentName, setAgentName] = React.useState('');

  function handleLogin(e) {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => { setLoading(false); setStep('onboard'); }, 1000);
  }

  function handleOnboard(e) {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => { setLoading(false); onLogin && onLogin(); }, 800);
  }

  const s = {
    page: { flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F9FAFB', padding: 24 },
    card: { background: '#fff', border: '1px solid #E5E7EB', borderRadius: 12, padding: '36px 40px', width: '100%', maxWidth: 400, boxShadow: '0 4px 6px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.06)' },
    logo: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 28 },
    mark: { width: 32, height: 32, background: '#6366F1', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' },
    wordmark: { fontSize: 16, fontWeight: 700, color: '#111827', letterSpacing: '-0.02em' },
    title: { fontSize: 22, fontWeight: 700, color: '#111827', letterSpacing: '-0.025em', marginBottom: 6 },
    sub: { fontSize: 14, color: '#6B7280', marginBottom: 28, lineHeight: 1.5 },
    label: { fontSize: 12, fontWeight: 500, color: '#374151', display: 'block', marginBottom: 5 },
    input: { width: '100%', fontFamily: 'var(--font-sans)', fontSize: 13, color: '#111827', background: '#fff', border: '1px solid #D1D5DB', borderRadius: 6, padding: '9px 12px', outline: 'none', boxSizing: 'border-box', transition: 'border-color 150ms, box-shadow 150ms' },
    fieldWrap: { marginBottom: 14 },
    divider: { display: 'flex', alignItems: 'center', gap: 10, margin: '20px 0', color: '#9CA3AF', fontSize: 12 },
    line: { flex: 1, height: 1, background: '#E5E7EB' },
    oauthBtn: { width: '100%', background: '#fff', border: '1px solid #D1D5DB', borderRadius: 6, padding: '8px 14px', fontSize: 13, fontWeight: 500, color: '#374151', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, fontFamily: 'inherit', boxShadow: '0 1px 2px rgba(0,0,0,0.04)', marginBottom: 10 },
  };

  if (step === 'login') {
    return (
      <div style={s.page}>
        <div style={s.card}>
          <div style={s.logo}>
            <div style={s.mark}><Icon name="terminal" size={16} color="white" /></div>
            <span style={s.wordmark}>OpenDevOps</span>
          </div>
          <div style={s.title}>Welcome back</div>
          <div style={s.sub}>Sign in to your workspace</div>

          <button style={s.oauthBtn}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>
            Continue with GitHub
          </button>

          <div style={s.divider}><div style={s.line}></div><span>or</span><div style={s.line}></div></div>

          <form onSubmit={handleLogin}>
            <div style={s.fieldWrap}>
              <label style={s.label}>Email</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.com" style={s.input}
                onFocus={e => { e.target.style.borderColor='#6366F1'; e.target.style.boxShadow='0 0 0 3px rgba(99,102,241,0.15)'; }}
                onBlur={e => { e.target.style.borderColor='#D1D5DB'; e.target.style.boxShadow='none'; }}
              />
            </div>
            <div style={s.fieldWrap}>
              <label style={s.label}>Password</label>
              <div style={{ position: 'relative' }}>
                <input type={showPass ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" style={{ ...s.input, paddingRight: 36 }}
                  onFocus={e => { e.target.style.borderColor='#6366F1'; e.target.style.boxShadow='0 0 0 3px rgba(99,102,241,0.15)'; }}
                  onBlur={e => { e.target.style.borderColor='#D1D5DB'; e.target.style.boxShadow='none'; }}
                />
                <button type="button" onClick={() => setShowPass(!showPass)} style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#9CA3AF', padding: 2 }}>
                  <Icon name={showPass ? 'eyeOff' : 'eye'} size={14} />
                </button>
              </div>
            </div>
            <div style={{ textAlign: 'right', marginBottom: 18 }}>
              <a href="#" style={{ fontSize: 12, color: '#6366F1', textDecoration: 'none' }}>Forgot password?</a>
            </div>
            <button type="submit" disabled={loading} style={{ width: '100%', background: loading ? '#818CF8' : '#6366F1', color: '#fff', border: 'none', borderRadius: 6, padding: '9px 14px', fontSize: 13, fontWeight: 600, cursor: loading ? 'default' : 'pointer', fontFamily: 'inherit', transition: 'background 120ms' }}>
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <div style={{ marginTop: 20, textAlign: 'center', fontSize: 13, color: '#6B7280' }}>
            No account? <a href="#" style={{ color: '#6366F1', fontWeight: 500 }}>Get started free</a>
          </div>
        </div>
      </div>
    );
  }

  // Onboarding
  return (
    <div style={s.page}>
      <div style={{ ...s.card, maxWidth: 460 }}>
        <div style={s.logo}>
          <div style={s.mark}><Icon name="terminal" size={16} color="white" /></div>
          <span style={s.wordmark}>OpenDevOps</span>
        </div>
        <div style={{ display: 'flex', gap: 6, marginBottom: 24 }}>
          {['Workspace', 'Agent setup', 'Invite team'].map((label, i) => (
            <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 5 }}>
              <div style={{ height: 3, borderRadius: 9999, background: i === 0 ? '#6366F1' : '#E5E7EB' }}></div>
              <span style={{ fontSize: 11, color: i === 0 ? '#4F46E5' : '#9CA3AF', fontWeight: 500 }}>{label}</span>
            </div>
          ))}
        </div>
        <div style={s.title}>Set up your workspace</div>
        <div style={s.sub}>You can always change these later in settings.</div>
        <form onSubmit={handleOnboard}>
          <div style={s.fieldWrap}>
            <label style={s.label}>Organization name</label>
            <input value={orgName} onChange={e => setOrgName(e.target.value)} placeholder="Acme Corp" style={s.input}
              onFocus={e => { e.target.style.borderColor='#6366F1'; e.target.style.boxShadow='0 0 0 3px rgba(99,102,241,0.15)'; }}
              onBlur={e => { e.target.style.borderColor='#D1D5DB'; e.target.style.boxShadow='none'; }}
            />
          </div>
          <div style={s.fieldWrap}>
            <label style={s.label}>Default agent name</label>
            <input value={agentName} onChange={e => setAgentName(e.target.value)} placeholder="prod-agent-01" style={{ ...s.input, fontFamily: 'var(--font-mono)' }}
              onFocus={e => { e.target.style.borderColor='#6366F1'; e.target.style.boxShadow='0 0 0 3px rgba(99,102,241,0.15)'; }}
              onBlur={e => { e.target.style.borderColor='#D1D5DB'; e.target.style.boxShadow='none'; }}
            />
            <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>Used as the identifier in logs and CLI</div>
          </div>
          <button type="submit" disabled={loading} style={{ width: '100%', background: loading ? '#818CF8' : '#6366F1', color: '#fff', border: 'none', borderRadius: 6, padding: '9px 14px', fontSize: 13, fontWeight: 600, cursor: loading ? 'default' : 'pointer', fontFamily: 'inherit', marginTop: 8 }}>
            {loading ? 'Setting up…' : 'Continue'}
          </button>
        </form>
      </div>
    </div>
  );
}

Object.assign(window, { Login });
