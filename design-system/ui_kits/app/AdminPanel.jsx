// Admin panel — team management, roles, permissions

function AdminPanel() {
  const [activeTab, setActiveTab] = React.useState('team');
  const [members, setMembers] = React.useState([
    { name: 'Jane Doe', email: 'jane@company.com', role: 'Admin', status: 'active', joined: 'Jan 12, 2025', avatarColor: '#6366F1' },
    { name: 'Carlos Ruiz', email: 'carlos@company.com', role: 'Engineer', status: 'active', joined: 'Feb 3, 2025', avatarColor: '#10B981' },
    { name: 'Priya Nair', email: 'priya@company.com', role: 'Engineer', status: 'active', joined: 'Mar 18, 2025', avatarColor: '#F59E0B' },
    { name: 'Tom Baker', email: 'tom@company.com', role: 'Viewer', status: 'inactive', joined: 'Apr 1, 2025', avatarColor: '#9CA3AF' },
    { name: 'Invited', email: 'dev@partner.io', role: 'Engineer', status: 'invited', joined: '—', avatarColor: '#C7D2FE' },
  ]);
  const [showInvite, setShowInvite] = React.useState(false);
  const [inviteEmail, setInviteEmail] = React.useState('');

  const roleColors = {
    Admin:    { bg: '#EEF2FF', color: '#4F46E5', border: '#C7D2FE' },
    Engineer: { bg: '#ECFDF5', color: '#059669', border: '#A7F3D0' },
    Viewer:   { bg: '#F3F4F6', color: '#6B7280', border: '#E5E7EB' },
  };
  const statusConfig = {
    active:   { variant: 'green', label: 'Active' },
    inactive: { variant: 'default', label: 'Inactive' },
    invited:  { variant: 'blue', label: 'Invited' },
  };

  const tabs = [
    { id: 'team', label: 'Team members' },
    { id: 'roles', label: 'Roles & permissions' },
    { id: 'audit', label: 'Audit log' },
  ];

  const s = {
    page: { flex: 1, overflow: 'auto', background: '#F9FAFB' },
    header: { background: '#fff', borderBottom: '1px solid #E5E7EB', padding: '16px 28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
    tabRow: { display: 'flex', gap: 0, borderBottom: '1px solid #E5E7EB', background: '#fff', padding: '0 28px' },
    tab: (active) => ({ padding: '10px 16px', fontSize: 13, fontWeight: 500, color: active ? '#4F46E5' : '#6B7280', borderBottom: active ? '2px solid #6366F1' : '2px solid transparent', cursor: 'pointer', transition: 'color 120ms', marginBottom: -1, background: 'none', border: 'none', fontFamily: 'inherit' }),
    content: { padding: '24px 28px' },
    card: { background: '#fff', border: '1px solid #E5E7EB', borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 2px rgba(0,0,0,0.04)' },
    th: { fontSize: 11, fontWeight: 600, color: '#9CA3AF', letterSpacing: '0.06em', textTransform: 'uppercase', padding: '10px 18px', textAlign: 'left', background: '#F9FAFB', borderBottom: '1px solid #E5E7EB' },
    td: { fontSize: 13, color: '#374151', padding: '12px 18px', borderBottom: '1px solid #F3F4F6', verticalAlign: 'middle' },
  };

  return (
    <div style={s.page}>
      <div style={s.header}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#111827' }}>Admin</div>
          <div style={{ fontSize: 13, color: '#6B7280', marginTop: 1 }}>Manage your team and permissions</div>
        </div>
        <Btn variant="primary" size="sm" icon="plus" onClick={() => setShowInvite(true)}>Invite member</Btn>
      </div>

      <div style={s.tabRow}>
        {tabs.map(t => (
          <button key={t.id} style={s.tab(activeTab === t.id)} onClick={() => setActiveTab(t.id)}>{t.label}</button>
        ))}
      </div>

      <div style={s.content}>
        {activeTab === 'team' && (
          <>
            {showInvite && (
              <div style={{ background: '#EEF2FF', border: '1px solid #C7D2FE', borderRadius: 8, padding: '14px 18px', marginBottom: 16, display: 'flex', gap: 10, alignItems: 'center' }}>
                <input value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} placeholder="colleague@company.com" style={{ flex: 1, fontFamily: 'var(--font-sans)', fontSize: 13, color: '#111827', background: '#fff', border: '1px solid #C7D2FE', borderRadius: 6, padding: '7px 10px', outline: 'none' }} />
                <select style={{ fontFamily: 'var(--font-sans)', fontSize: 13, color: '#374151', background: '#fff', border: '1px solid #C7D2FE', borderRadius: 6, padding: '7px 10px', outline: 'none' }}>
                  <option>Engineer</option>
                  <option>Admin</option>
                  <option>Viewer</option>
                </select>
                <Btn variant="primary" size="sm">Send invite</Btn>
                <button onClick={() => setShowInvite(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9CA3AF' }}><Icon name="x" size={16} /></button>
              </div>
            )}

            <div style={s.card}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={s.th}>Member</th>
                    <th style={s.th}>Role</th>
                    <th style={s.th}>Status</th>
                    <th style={s.th}>Joined</th>
                    <th style={{ ...s.th, width: 40 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((m, i) => (
                    <tr key={i} onMouseEnter={e => e.currentTarget.style.background='#F9FAFB'} onMouseLeave={e => e.currentTarget.style.background='transparent'}>
                      <td style={s.td}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <Avatar name={m.name} size={28} color={m.avatarColor} />
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 500, color: '#111827' }}>{m.name}</div>
                            <div style={{ fontSize: 12, color: '#6B7280' }}>{m.email}</div>
                          </div>
                        </div>
                      </td>
                      <td style={s.td}>
                        <span style={{ background: roleColors[m.role]?.bg, color: roleColors[m.role]?.color, border: `1px solid ${roleColors[m.role]?.border}`, borderRadius: 4, fontSize: 11, fontWeight: 500, padding: '2px 7px' }}>{m.role}</span>
                      </td>
                      <td style={s.td}><Badge variant={statusConfig[m.status].variant} dot>{statusConfig[m.status].label}</Badge></td>
                      <td style={{ ...s.td, color: '#6B7280', fontSize: 12, borderBottom: i === members.length - 1 ? 'none' : '1px solid #F3F4F6' }}>{m.joined}</td>
                      <td style={{ ...s.td, borderBottom: i === members.length - 1 ? 'none' : '1px solid #F3F4F6' }}>
                        <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9CA3AF', padding: 4 }}><Icon name="moreHoriz" size={16} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {activeTab === 'roles' && (
          <div style={s.card}>
            {[
              { role: 'Admin', desc: 'Full access — manage agents, team, billing, and settings', perms: ['Deploy agents', 'Manage env vars', 'Invite members', 'Delete pipelines', 'View audit log'] },
              { role: 'Engineer', desc: 'Can deploy and manage pipelines; cannot manage team', perms: ['Deploy agents', 'Manage env vars', 'View pipelines'] },
              { role: 'Viewer', desc: 'Read-only access to dashboards and logs', perms: ['View dashboard', 'View logs'] },
            ].map((r, i) => (
              <div key={i} style={{ padding: '16px 18px', borderBottom: i < 2 ? '1px solid #F3F4F6' : 'none' }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>{r.role}</span>
                  <span style={{ fontSize: 12, color: '#6B7280' }}>{r.desc}</span>
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {r.perms.map((p, j) => (
                    <span key={j} style={{ background: '#F3F4F6', color: '#6B7280', border: '1px solid #E5E7EB', borderRadius: 4, fontSize: 11, fontWeight: 500, padding: '2px 7px', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      <Icon name="check" size={10} color="#10B981" />{p}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'audit' && (
          <div style={s.card}>
            {[
              { user: 'Jane Doe', action: 'Deployed prod-agent-01', time: '10:42 AM', type: 'deploy' },
              { user: 'Carlos Ruiz', action: 'Updated API_KEY secret', time: '9:18 AM', type: 'secret' },
              { user: 'Priya Nair', action: 'Rolled back to v2.3.0', time: 'Yesterday', type: 'rollback' },
              { user: 'Jane Doe', action: 'Invited dev@partner.io', time: 'Yesterday', type: 'invite' },
              { user: 'Tom Baker', action: 'Viewed deployment logs', time: '2d ago', type: 'view' },
            ].map((e, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 18px', borderBottom: i < 4 ? '1px solid #F3F4F6' : 'none' }}>
                <Avatar name={e.user} size={26} color="#6366F1" />
                <div style={{ flex: 1 }}>
                  <span style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>{e.user} </span>
                  <span style={{ fontSize: 13, color: '#6B7280' }}>{e.action}</span>
                </div>
                <span style={{ fontSize: 12, color: '#9CA3AF', whiteSpace: 'nowrap' }}>{e.time}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { AdminPanel });
