import { Plus, X, LayoutDashboard } from 'lucide-react';
import { Link, useMatch } from 'react-router-dom';
import { cn, relativeTime } from '../lib/utils';
import type { Session } from '../types';

interface Props {
  sessions: Session[];
  currentSessionId: string;
  onNew: () => void;
  onSwitch: (id: string) => void;
  onDelete: (id: string) => void;
}

function DashboardLink() {
  const active = useMatch('/dashboard');
  return (
    <Link
      to="/dashboard"
      className={cn(
        'w-full px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 border transition-colors',
        active
          ? 'text-gray-100 bg-gray-700/60 border-gray-600'
          : 'text-gray-400 border-transparent hover:bg-gray-700/40 hover:text-gray-100',
      )}
    >
      <LayoutDashboard size={14} />
      Dashboard
    </Link>
  );
}

export default function Sidebar({ sessions, currentSessionId, onNew, onSwitch, onDelete }: Props) {
  return (
    <aside className="w-[260px] shrink-0 bg-gray-800 border-r border-gray-700 flex flex-col overflow-hidden">
      <div className="p-3 border-b border-gray-700 shrink-0 flex flex-col gap-1.5">
        <DashboardLink />
        <button
          onClick={onNew}
          className="w-full px-3 py-2 rounded-lg text-emerald-400 text-sm font-medium flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/15 hover:border-emerald-500/35 transition-colors text-left"
        >
          <Plus size={14} />
          New chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-1.5 flex flex-col gap-px">
        {sessions.length === 0 ? (
          <p className="px-3 py-6 text-xs text-gray-500 text-center leading-relaxed">
            No past sessions yet.<br />Start a conversation to save it.
          </p>
        ) : (
          sessions.map(s => (
            <div
              key={s.id}
              onClick={() => onSwitch(s.id)}
              className={cn(
                'px-2.5 py-2 rounded-lg cursor-pointer flex flex-col gap-0.5 relative border transition-colors group',
                s.id === currentSessionId
                  ? 'bg-gray-700/60 border-gray-600'
                  : 'border-transparent hover:bg-gray-700/40',
              )}
            >
              <div className="text-sm text-gray-100 truncate pr-6">
                {s.title ?? 'Untitled session'}
              </div>
              <div className="text-xs text-gray-500">
                {s.last_active_at ? relativeTime(s.last_active_at) : ''}
              </div>
              <button
                title="Delete session"
                onClick={e => { e.stopPropagation(); onDelete(s.id); }}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-all p-1 rounded"
              >
                <X size={13} />
              </button>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
