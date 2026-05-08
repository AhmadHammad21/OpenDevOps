import { useState } from 'react';
import { Plus, X, LayoutDashboard, MessageSquare, Terminal, GitBranch, Users, Settings, LogOut } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { cn, relativeTime } from '../lib/utils';
import { useAuth } from '../context/AuthContext';
import type { Session } from '../types';

interface Props {
  sessions: Session[];
  currentSessionId: string;
  onNew: () => void;
  onSwitch: (id: string) => void;
  onDelete: (id: string) => void;
}

interface NavItemProps {
  to: string;
  matchPrefix?: string;
  icon: React.ReactNode;
  label: string;
  badge?: string;
  badgeRed?: boolean;
  disabled?: boolean;
}

function NavItem({ to, matchPrefix, icon, label, badge, badgeRed, disabled }: NavItemProps) {
  const { pathname } = useLocation();
  const prefix = matchPrefix ?? to;
  const active = pathname === prefix || pathname.startsWith(prefix + '/');

  if (disabled) {
    return (
      <div className="w-full flex items-center gap-2 px-3.5 py-[7px] text-[13px] font-medium text-gray-300 dark:text-[#3F3F47] cursor-not-allowed select-none relative">
        <span className="shrink-0">{icon}</span>
        <span className="flex-1">{label}</span>
      </div>
    );
  }

  return (
    <Link
      to={to}
      className={cn(
        'relative w-full flex items-center gap-2 px-3.5 py-[7px] text-[13px] font-medium transition-all duration-100',
        active
          ? 'text-indigo-500 dark:text-[#818CF8] bg-indigo-50 dark:bg-[#1E1B4B]'
          : 'text-gray-500 dark:text-[#94A3B8] hover:bg-gray-100 dark:hover:bg-[#27272F] hover:text-gray-700 dark:hover:text-[#F1F5F9]',
      )}
    >
      {active && (
        <span className="absolute left-0 inset-y-1 w-[3px] bg-indigo-500 dark:bg-[#818CF8] rounded-r" />
      )}
      <span className="shrink-0">{icon}</span>
      <span className="flex-1">{label}</span>
      {badge && (
        <span className={cn(
          'text-[10px] font-semibold px-1.5 py-px rounded-full font-mono',
          badgeRed
            ? 'bg-red-50 dark:bg-[#2D1515] text-red-600 dark:text-[#F87171]'
            : 'bg-indigo-50 dark:bg-[#1E1B4B] text-indigo-500 dark:text-[#818CF8]',
        )}>
          {badge}
        </span>
      )}
    </Link>
  );
}

export default function Sidebar({ sessions, currentSessionId, onNew, onSwitch, onDelete }: Props) {
  const [hovSession, setHovSession] = useState<string | null>(null);
  const navigate = useNavigate();
  const { user, isAdmin, authRequired, logout } = useAuth();
  const displayName = user?.name || 'You';
  const displayRole = isAdmin ? 'Admin' : 'User';

  const currentChatTo = currentSessionId ? `/chat/${currentSessionId}` : '/';

  return (
    <aside className="w-[240px] shrink-0 bg-white dark:bg-[#18181C] border-r border-gray-200 dark:border-[#27272F] flex flex-col h-full overflow-hidden">

      {/* Logo */}
      <div className="px-3.5 py-[14px] border-b border-gray-200 dark:border-[#27272F] flex items-center gap-[9px] shrink-0">
        <div className="w-7 h-7 bg-indigo-500 rounded-[7px] flex items-center justify-center shrink-0">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
          </svg>
        </div>
        <span className="text-[14px] font-bold text-gray-900 dark:text-[#F1F5F9] tracking-[-0.02em]">OpenDevOps</span>
      </div>

      {/* Primary nav */}
      <div className="pt-2 shrink-0">
        <NavItem to="/dashboard"    icon={<LayoutDashboard size={14} />} label="Dashboard" />
        <NavItem to={currentChatTo} icon={<MessageSquare   size={14} />} label="Chat"       matchPrefix="/chat" />
        <NavItem to="/history"      icon={<Terminal        size={14} />} label="Agent logs" />
        <NavItem to="/dashboard"    icon={<GitBranch       size={14} />} label="Pipelines"  disabled />
      </div>

      {/* Conversations label */}
      <div className="px-3.5 pt-4 pb-1 flex items-center justify-between shrink-0">
        <span className="text-[10px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.09em]">
          Conversations
        </span>
        <button
          onClick={onNew}
          className="text-gray-400 dark:text-[#64748B] hover:text-indigo-500 dark:hover:text-[#818CF8] transition-colors p-0.5 rounded"
          title="New chat"
        >
          <Plus size={13} />
        </button>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto pb-2">
        {sessions.length === 0 ? (
          <p className="px-3.5 py-4 text-xs text-gray-400 dark:text-[#64748B] text-center leading-relaxed">
            No past sessions yet.
          </p>
        ) : (
          sessions.map(s => (
            <div
              key={s.id}
              onClick={() => onSwitch(s.id)}
              onMouseEnter={() => setHovSession(s.id)}
              onMouseLeave={() => setHovSession(null)}
              className={cn(
                'px-3.5 py-[7px] cursor-pointer relative transition-all duration-100 border-l-2',
                s.id === currentSessionId
                  ? 'border-indigo-500 dark:border-[#818CF8] bg-indigo-50 dark:bg-[#1E1B4B]'
                  : 'border-transparent hover:bg-gray-100 dark:hover:bg-[#27272F]',
              )}
            >
              <div className={cn(
                'text-[13px] truncate pr-5',
                s.id === currentSessionId ? 'font-medium text-gray-900 dark:text-[#F1F5F9]' : 'text-gray-700 dark:text-[#CBD5E1]',
              )}>
                {s.title ?? 'Untitled session'}
              </div>
              <div className="text-[11px] text-gray-400 dark:text-[#64748B] mt-px">
                {s.last_active_at ? relativeTime(s.last_active_at) : ''}
              </div>
              {hovSession === s.id && (
                <button
                  title="Delete session"
                  onClick={e => { e.stopPropagation(); onDelete(s.id); }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 dark:text-[#64748B] hover:text-red-500 dark:hover:text-[#F87171] transition-colors p-1 rounded"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          ))
        )}
      </div>

      {/* Admin section */}
      <div className="border-t border-gray-200 dark:border-[#27272F] shrink-0">
        <div className="px-3.5 pt-2 pb-1">
          <span className="text-[10px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.09em]">Admin</span>
        </div>
        {isAdmin && <NavItem to="/users" icon={<Users size={14} />} label="Team" />}
        <NavItem to="/settings" icon={<Settings size={14} />} label="Settings" />
      </div>

      {/* User footer */}
      <div className="flex items-center gap-2 px-3.5 py-2.5 border-t border-gray-200 dark:border-[#27272F] shrink-0">
        <div
          className="flex items-center gap-2 flex-1 min-w-0 cursor-pointer hover:bg-gray-50 dark:hover:bg-[#27272F] rounded-md px-1 py-0.5 transition-colors"
          onClick={() => navigate('/settings')}
        >
          <div className="w-[26px] h-[26px] rounded-full bg-indigo-500 flex items-center justify-center text-white text-[10px] font-semibold shrink-0">
            {displayName.slice(0, 2).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[12px] font-medium text-gray-900 dark:text-[#F1F5F9] truncate">{displayName}</div>
            <div className="text-[11px] text-gray-400 dark:text-[#64748B]">{displayRole}</div>
          </div>
        </div>
        <button
          onClick={logout}
          title="Sign out"
          className="p-1 rounded text-gray-400 dark:text-[#64748B] hover:text-red-500 dark:hover:text-[#F87171] transition-colors shrink-0"
        >
          <LogOut size={13} />
        </button>
      </div>
    </aside>
  );
}
