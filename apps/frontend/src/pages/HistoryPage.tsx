import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, Clock, MessageSquare, RefreshCw, Search, Wrench, Zap } from 'lucide-react';
import { fetchHistory, fetchSessions, searchHistory } from '../lib/api';
import { relativeTime } from '../lib/utils';
import type { HistoryStats, SearchResult, Session } from '../types';

const DAYS_OPTIONS = [7, 30, 90] as const;
type Days = typeof DAYS_OPTIONS[number];

function StatCard({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 dark:border-[#1E222B] flex items-center gap-2">
        <span className="text-indigo-500 dark:text-[#00A3FF]">{icon}</span>
        <span className="text-[12px] font-semibold text-gray-700 dark:text-[#CBD5E1] uppercase tracking-[0.06em]">{title}</span>
      </div>
      <div className="divide-y divide-gray-100 dark:divide-[#1E222B]">{children}</div>
    </div>
  );
}

function EmptyRow({ label }: { label: string }) {
  return (
    <div className="px-4 py-3 text-[12px] text-gray-400 dark:text-[#64748B] italic">{label}</div>
  );
}

export default function HistoryPage() {
  const [days, setDays] = useState<Days>(30);
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [statsLoading, setStatsLoading] = useState(true);
  const [sessionsLoading, setSessionsLoading] = useState(true);

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadStats = (d: Days) => {
    setStatsLoading(true);
    fetchHistory(d)
      .then(setStats)
      .catch(() => {})
      .finally(() => setStatsLoading(false));
  };

  const loadSessions = () => {
    setSessionsLoading(true);
    fetchSessions()
      .then(setSessions)
      .catch(() => {})
      .finally(() => setSessionsLoading(false));
  };

  useEffect(() => { loadStats(days); }, [days]);
  useEffect(() => { loadSessions(); }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!searchQuery.trim()) { setSearchResults(null); return; }
    debounceRef.current = setTimeout(() => {
      setSearching(true);
      searchHistory(searchQuery.trim())
        .then(setSearchResults)
        .catch(() => setSearchResults([]))
        .finally(() => setSearching(false));
    }, 350);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [searchQuery]);

  const maxAlarm  = stats?.top_alarms[0]?.session_count  ?? 1;
  const maxLambda = stats?.top_lambdas[0]?.session_count ?? 1;

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-gray-50 dark:bg-[#000000] min-h-0">
      {/* Header */}
      <div className="bg-white dark:bg-[#0A0C10] border-b border-gray-200 dark:border-[#1E222B] px-7 py-[14px] flex items-center justify-between shrink-0 gap-4">
        <div>
          <div className="text-[16px] font-bold text-gray-900 dark:text-[#E4E1EA] tracking-[-0.02em]">Investigation History</div>
          <div className="text-[14px] text-gray-500 dark:text-[#94A3B8] mt-0.5">Cross-session patterns, top resources, recurring errors</div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {/* Days filter */}
          <div className="flex rounded-[5px] border border-gray-200 dark:border-[#2A2F3A] overflow-hidden text-[13px] font-medium">
            {DAYS_OPTIONS.map(d => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-2.5 py-[5px] transition-colors ${
                  days === d
                    ? 'bg-indigo-500 dark:bg-[#010978] text-white'
                    : 'bg-white dark:bg-[#0A0C10] text-gray-600 dark:text-[#94A3B8] hover:bg-gray-50 dark:hover:bg-[#1E222B]'
                }`}
              >{d}d</button>
            ))}
          </div>
          <button
            onClick={() => { loadStats(days); loadSessions(); }}
            className="flex items-center gap-1.5 text-[13px] font-medium text-gray-600 dark:text-[#94A3B8] bg-white dark:bg-[#0A0C10] hover:bg-gray-50 dark:hover:bg-[#1E222B] border border-gray-300 dark:border-[#2A2F3A] rounded-[5px] px-2.5 py-[5px] shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-colors"
          >
            <RefreshCw size={12} />
            Refresh
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-7 flex flex-col gap-5">
        {/* Search bar */}
        <div className="relative max-w-lg">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-[#64748B]" />
          <input
            type="text"
            placeholder="Search past investigations…"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-2 text-[14px] bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#2A2F3A] rounded-lg text-gray-900 dark:text-[#E4E1EA] placeholder-gray-400 dark:placeholder-[#64748B] focus:outline-none focus:ring-2 focus:ring-indigo-300 dark:focus:ring-[#010978] transition"
          />
          {searching && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <div className="spinner-dots"><span /><span /><span /></div>
            </div>
          )}
        </div>

        {/* Search results */}
        {searchResults !== null ? (
          <div className="flex flex-col gap-2 max-w-2xl">
            <div className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">
              {searchResults.length} result{searchResults.length !== 1 ? 's' : ''} for "{searchQuery}"
            </div>
            {searchResults.length === 0 ? (
              <div className="text-[13px] text-gray-400 dark:text-[#64748B] italic">No sessions matched.</div>
            ) : searchResults.map(r => (
              <Link
                key={r.id}
                to={`/chat/${r.id}`}
                className="block bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg p-4 hover:border-indigo-200 dark:hover:border-[#0E4FA6] hover:shadow-[0_0_0_3px_rgba(99,102,241,0.06)] dark:hover:shadow-[0_0_0_3px_rgba(129,140,248,0.08)] transition-all group"
                onClick={() => localStorage.setItem('devops-session-id', r.id)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <MessageSquare size={14} className="text-indigo-400 dark:text-[#00A3FF] shrink-0 mt-0.5" />
                    <span className="text-[14px] text-gray-900 dark:text-[#E4E1EA] font-medium truncate group-hover:text-indigo-500 dark:group-hover:text-[#00A3FF] transition-colors">
                      {r.title ?? 'Untitled session'}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 text-[11px] text-gray-400 dark:text-[#64748B] shrink-0">
                    <Clock size={11} />
                    {r.last_active_at ? relativeTime(r.last_active_at) : ''}
                  </div>
                </div>
                {r.snippet && (
                  <p className="mt-1.5 ml-5 text-[13px] text-gray-500 dark:text-[#94A3B8] line-clamp-2 leading-relaxed">{r.snippet}</p>
                )}
              </Link>
            ))}
          </div>
        ) : (
          <>
            {/* Analytics cards */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Top Alarms */}
              <StatCard title={`Top Alarms — last ${days}d`} icon={<Bell size={13} />}>
                {statsLoading ? (
                  <div className="px-4 py-3 flex items-center gap-2 text-[12px] text-gray-400 dark:text-[#64748B]">
                    <div className="spinner-dots"><span /><span /><span /></div> Loading…
                  </div>
                ) : !stats?.top_alarms.length ? (
                  <EmptyRow label="No alarm lookups in this period" />
                ) : stats.top_alarms.map((a, i) => (
                  <div key={i} className="px-4 py-2.5 flex flex-col gap-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[13px] font-mono text-gray-800 dark:text-[#CBD5E1] truncate">{a.alarm_name}</span>
                      <span className="text-[11px] text-gray-400 dark:text-[#64748B] shrink-0">{a.session_count} session{a.session_count !== 1 ? 's' : ''}</span>
                    </div>
                    <div className="h-1 rounded-full bg-gray-100 dark:bg-[#1E222B] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-indigo-400 dark:bg-[#00A3FF]"
                        style={{ width: `${Math.round((a.session_count / maxAlarm) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </StatCard>

              {/* Top Lambda Functions */}
              <StatCard title={`Top Lambda Functions — last ${days}d`} icon={<Zap size={13} />}>
                {statsLoading ? (
                  <div className="px-4 py-3 flex items-center gap-2 text-[12px] text-gray-400 dark:text-[#64748B]">
                    <div className="spinner-dots"><span /><span /><span /></div> Loading…
                  </div>
                ) : !stats?.top_lambdas.length ? (
                  <EmptyRow label="No Lambda investigations in this period" />
                ) : stats.top_lambdas.map((l, i) => (
                  <div key={i} className="px-4 py-2.5 flex flex-col gap-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[13px] font-mono text-gray-800 dark:text-[#CBD5E1] truncate">{l.function_name}</span>
                      <span className="text-[11px] text-gray-400 dark:text-[#64748B] shrink-0">{l.session_count} session{l.session_count !== 1 ? 's' : ''}</span>
                    </div>
                    <div className="h-1 rounded-full bg-gray-100 dark:bg-[#1E222B] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-emerald-400 dark:bg-[#00A3FF]"
                        style={{ width: `${Math.round((l.session_count / maxLambda) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </StatCard>
            </div>

            {/* Recurring Tool Errors */}
            {(stats?.recurring_errors.length ?? 0) > 0 && (
              <StatCard title={`Recurring Tool Errors — last ${days}d`} icon={<Wrench size={13} />}>
                {stats!.recurring_errors.map((e, i) => (
                  <div key={i} className="px-4 py-2.5 flex items-start gap-3">
                    <span className="text-[11px] font-mono bg-red-50 dark:bg-[#1C1010] text-red-500 dark:text-[#F87171] px-1.5 py-0.5 rounded shrink-0 mt-0.5">{e.tool_name}</span>
                    <span className="text-[12px] text-gray-600 dark:text-[#94A3B8] flex-1 leading-snug">{e.error_snippet}</span>
                    <span className="text-[11px] text-gray-400 dark:text-[#64748B] shrink-0">×{e.count}</span>
                  </div>
                ))}
              </StatCard>
            )}

            {/* Investigation frequency trend */}
            {(stats?.trend.length ?? 0) > 0 && (
              <div className="bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-100 dark:border-[#1E222B] flex items-center gap-2">
                  <Clock size={13} className="text-indigo-500 dark:text-[#00A3FF]" />
                  <span className="text-[12px] font-semibold text-gray-700 dark:text-[#CBD5E1] uppercase tracking-[0.06em]">Investigation Frequency</span>
                </div>
                <div className="px-4 py-3 flex items-end gap-1 h-20">
                  {(() => {
                    const max = Math.max(...(stats?.trend.map(t => t.count) ?? [1]), 1);
                    return stats!.trend.map((t, i) => (
                      <div key={i} className="flex-1 flex flex-col items-center gap-0.5 group relative" title={`${t.date}: ${t.count}`}>
                        <div
                          className="w-full rounded-sm bg-indigo-200 dark:bg-[#312E81] group-hover:bg-indigo-400 dark:group-hover:bg-[#00A3FF] transition-colors"
                          style={{ height: `${Math.max(3, Math.round((t.count / max) * 52))}px` }}
                        />
                      </div>
                    ));
                  })()}
                </div>
                <div className="px-4 pb-2 flex justify-between text-[10px] text-gray-400 dark:text-[#64748B]">
                  <span>{stats!.trend[0]?.date}</span>
                  <span>{stats!.trend[stats!.trend.length - 1]?.date}</span>
                </div>
              </div>
            )}

            {/* All sessions list */}
            <div className="flex flex-col gap-2 max-w-2xl">
              <div className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em] mb-1">
                {sessionsLoading ? 'Loading…' : `${sessions.length} session${sessions.length !== 1 ? 's' : ''}`}
              </div>
              {sessionsLoading ? (
                <div className="flex items-center gap-2 text-sm text-gray-400 dark:text-[#64748B]">
                  <div className="spinner-dots"><span /><span /><span /></div>
                  Loading…
                </div>
              ) : sessions.length === 0 ? (
                <div className="text-sm text-gray-400 dark:text-[#64748B] text-center mt-8">No sessions yet.</div>
              ) : sessions.map(s => (
                <Link
                  key={s.id}
                  to={`/chat/${s.id}`}
                  className="block bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg p-4 hover:border-indigo-200 dark:hover:border-[#0E4FA6] hover:shadow-[0_0_0_3px_rgba(99,102,241,0.06)] dark:hover:shadow-[0_0_0_3px_rgba(129,140,248,0.08)] transition-all group"
                  onClick={() => localStorage.setItem('devops-session-id', s.id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <MessageSquare size={14} className="text-indigo-400 dark:text-[#00A3FF] shrink-0 mt-0.5" />
                      <span className="text-[14px] text-gray-900 dark:text-[#E4E1EA] font-medium truncate group-hover:text-indigo-500 dark:group-hover:text-[#00A3FF] transition-colors">
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
          </>
        )}
      </div>
    </div>
  );
}
