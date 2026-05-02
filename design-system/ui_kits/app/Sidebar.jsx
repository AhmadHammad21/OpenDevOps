// Sidebar navigation component

function Sidebar({ currentPage, onNavigate }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
    { id: 'chat',      label: 'Chat',      icon: 'chat',     badge: '2' },
    { id: 'pipelines', label: 'Pipelines', icon: 'pipeline' },
    { id: 'logs',      label: 'Agent logs', icon: 'logs',    badge: '1', badgeVariant: 'red' },
  ];
  const adminItems = [
    { id: 'team',     label: 'Team',     icon: 'team' },
    { id: 'settings', label: 'Settings', icon: 'settings' },
  ];

  const sidebarStyles = {
    sidebar: { width: 220, background: '#fff', borderRight: '1px solid #E5E7EB', display: 'flex', flexDirection: 'column', height: '100%', flexShrink: 0 },
    logoRow: { display: 'flex', alignItems: 'center', gap: 8, padding: '14px 14px 12px', borderBottom: '1px solid #F3F4F6' },
    logoMark: { width: 26, height: 26, background: '#6366F1', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
    logoText: { fontSize: 13, fontWeight: 600, color: '#111827' },
    sectionLabel: { fontSize: 10, fontWeight: 600, color: '#9CA3AF', letterSpacing: '0.09em', textTransform: 'uppercase', padding: '10px 14px 4px' },
    spacer: { flex: 1 },
    userRow: { display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderTop: '1px solid #F3F4F6', cursor: 'pointer' },
  };

  function NavItem({ item }) {
    const active = currentPage === item.id;
    return (
      <div onClick={() => onNavigate(item.id)} style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '7px 14px', fontSize: 13, fontWeight: 500,
        color: active ? '#4F46E5' : '#6B7280',
        background: active ? '#EEF2FF' : 'transparent',
        cursor: 'pointer', position: 'relative',
        transition: 'background 120ms, color 120ms',
      }}
      onMouseEnter={e => { if (!active) { e.currentTarget.style.background = '#F3F4F6'; e.currentTarget.style.color = '#374151'; }}}
      onMouseLeave={e => { if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#6B7280'; }}}
      >
        {active && <span style={{ position: 'absolute', left: 0, top: 4, bottom: 4, width: 2.5, background: '#6366F1', borderRadius: '0 2px 2px 0' }}></span>}
        <Icon name={item.icon} size={15} color="currentColor" />
        <span style={{ flex: 1 }}>{item.label}</span>
        {item.badge && (
          <span style={{
            background: item.badgeVariant === 'red' ? '#FFF1F2' : '#EEF2FF',
            color: item.badgeVariant === 'red' ? '#E11D48' : '#4F46E5',
            fontSize: 10, fontWeight: 600, padding: '1px 5px', borderRadius: 9999,
            fontFamily: 'var(--font-mono)',
          }}>{item.badge}</span>
        )}
      </div>
    );
  }

  return (
    <div style={sidebarStyles.sidebar}>
      <div style={sidebarStyles.logoRow}>
        <div style={sidebarStyles.logoMark}>
          <Icon name="terminal" size={14} color="white" />
        </div>
        <span style={sidebarStyles.logoText}>OpenDevOps</span>
      </div>

      <div style={{ paddingTop: 8 }}>
        {navItems.map(item => <NavItem key={item.id} item={item} />)}
      </div>

      <div style={sidebarStyles.sectionLabel}>Admin</div>
      {adminItems.map(item => <NavItem key={item.id} item={item} />)}

      <div style={sidebarStyles.spacer}></div>

      <div style={sidebarStyles.userRow}>
        <Avatar name="Jane Doe" size={26} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: '#374151', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Jane Doe</div>
          <div style={{ fontSize: 11, color: '#9CA3AF' }}>Admin</div>
        </div>
        <Icon name="logout" size={14} color="#9CA3AF" />
      </div>
    </div>
  );
}

Object.assign(window, { Sidebar });
