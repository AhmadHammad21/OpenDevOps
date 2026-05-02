import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { MessageSquare, Clock, RefreshCw } from 'lucide-react';
import { fetchSessions } from '../lib/api';
import { relativeTime } from '../lib/utils';
import type { Session } from '../types';

export default function HistoryPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    fetchSessions()
      .then(setSessions)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-gray-50 dark:bg-[#0F0F12] min-h-0">
      {/* Page header */}
      <div className="bg-white dark:bg-[#18181C] border-b border-gray-200 dark:border-[#27272F] px-7 py-[14px] flex items-center justify-between shrink-0">
        <div>
          <div className="text-[16px] font-bold text-gray-900 dark:text-[#F1F5F9] tracking-[-0.02em]">Agent logs</div>
          <div className="text-[13px] text-gray-500 dark:text-[#94A3B8] mt-0.5">Real-time output from agent runs</div>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-1.5 text-[12px] font-medium text-gray-600 dark:text-[#94A3B8] bg-white dark:bg-[#18181C] hover:bg-gray-50 dark:hover:bg-[#27272F] border border-gray-300 dark:border-[#3F3F47] rounded-[5px] px-2.5 py-[5px] shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-colors"
        >
          <RefreshCw size={12} />
          Refresh
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-7">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-gray-400 dark:text-[#64748B]">
            <div className="spinner-dots"><span /><span /><span /></div>
            Loading…
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-sm text-gray-400 dark:text-[#64748B] text-center mt-16">No sessions yet.</div>
        ) : (
          <div className="flex flex-col gap-2 max-w-2xl">
            <div className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em] mb-1">
              {sessions.length} session{sessions.length !== 1 ? 's' : ''}
            </div>
            {sessions.map(s => (
              <Link
                key={s.id}
                to={`/chat/${s.id}`}
                className="block bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-lg p-4 hover:border-indigo-200 dark:hover:border-[#3730A3] hover:shadow-[0_0_0_3px_rgba(99,102,241,0.06)] dark:hover:shadow-[0_0_0_3px_rgba(129,140,248,0.08)] transition-all group"
                onClick={() => localStorage.setItem('devops-session-id', s.id)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <MessageSquare size={14} className="text-indigo-400 dark:text-[#818CF8] shrink-0 mt-0.5" />
                    <span className="text-[13px] text-gray-900 dark:text-[#F1F5F9] font-medium truncate group-hover:text-indigo-500 dark:group-hover:text-[#818CF8] transition-colors">
                      {s.title ?? 'Untitled session'}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 text-[11px] text-gray-400 dark:text-[#64748B] shrink-0">
                    <Clock size={11} />
                    {s.last_active_at ? relativeTime(s.last_active_at) : ''}
                  </div>
                </div>
                {s.model && (
                  <div className="mt-1.5 ml-5 text-[11px] text-gray-400 dark:text-[#64748B] font-mono">{s.model}</div>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
