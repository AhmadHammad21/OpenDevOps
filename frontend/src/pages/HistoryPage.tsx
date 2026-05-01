import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, MessageSquare, Clock } from 'lucide-react';
import { fetchSessions } from '../lib/api';
import { relativeTime } from '../lib/utils';
import type { Session } from '../types';

export default function HistoryPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSessions()
      .then(setSessions)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-700 bg-gray-800 flex items-center gap-4 shrink-0">
        <Link
          to="/"
          className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-100 transition-colors"
        >
          <ArrowLeft size={14} />
          Back
        </Link>
        <h1 className="text-sm font-semibold text-gray-100">Session History</h1>
        <span className="text-xs text-gray-500 ml-auto">{sessions.length} sessions</span>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <div className="spinner-dots"><span /><span /><span /></div>
            Loading…
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-sm text-gray-500 text-center mt-16">No sessions yet.</div>
        ) : (
          <div className="flex flex-col gap-2 max-w-2xl">
            {sessions.map(s => (
              <Link
                key={s.id}
                to="/"
                className="block border border-gray-700 rounded-lg p-4 hover:border-gray-600 hover:bg-gray-800/50 transition-colors group"
                onClick={() => localStorage.setItem('devops-session-id', s.id)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <MessageSquare size={14} className="text-emerald-500 shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-100 font-medium truncate group-hover:text-emerald-400 transition-colors">
                      {s.title ?? 'Untitled session'}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-gray-500 shrink-0">
                    <Clock size={11} />
                    {s.last_active_at ? relativeTime(s.last_active_at) : ''}
                  </div>
                </div>
                {s.model && (
                  <div className="mt-1.5 ml-5 text-xs text-gray-600 font-mono">{s.model}</div>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
