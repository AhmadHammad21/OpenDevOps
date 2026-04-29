import { relativeTime } from '../lib/utils';
import type { Session } from '../types';

interface Props {
  sessions: Session[];
  currentSessionId: string;
  onNew: () => void;
  onSwitch: (id: string) => void;
  onDelete: (id: string) => void;
}

export default function Sidebar({ sessions, currentSessionId, onNew, onSwitch, onDelete }: Props) {
  return (
    <aside id="sidebar">
      <div className="sidebar-header">
        <button id="new-chat-btn" onClick={onNew}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New chat
        </button>
      </div>
      <div id="session-list">
        {sessions.length === 0 ? (
          <div className="sessions-empty">No past sessions yet.<br />Start a conversation to save it.</div>
        ) : (
          sessions.map(s => (
            <div
              key={s.id}
              className={`session-item${s.id === currentSessionId ? ' active' : ''}`}
              onClick={() => onSwitch(s.id)}
            >
              <div className="si-title">{s.title ?? 'Untitled session'}</div>
              <div className="si-meta">{s.last_active_at ? relativeTime(s.last_active_at) : ''}</div>
              <button
                className="si-del"
                title="Delete session"
                onClick={e => { e.stopPropagation(); onDelete(s.id); }}
              >
                ×
              </button>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
