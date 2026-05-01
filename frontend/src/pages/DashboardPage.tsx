import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { MessageSquare, Wrench, Zap, DollarSign, Clock, AlertTriangle } from 'lucide-react';
import { fmtCost, fmtTok, relativeTime, cn } from '../lib/utils';

interface Summary {
  total_sessions: number;
  total_queries: number;
  total_tool_calls: number;
  total_tool_errors: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
}

interface ActivityDay  { date: string; sessions: number; }
interface TopTool       { tool: string; count: number; errors: number; }
interface ServiceEntry  { service: string; calls: number; pct: number; }
interface RecentSession {
  id: string; title: string | null; last_active_at: string | null;
  model: string | null; query_count: number; tool_count: number; cost_usd: number;
}

interface Stats {
  summary: Summary;
  activity: ActivityDay[];
  top_tools: TopTool[];
  service_breakdown: ServiceEntry[];
  recent_sessions: RecentSession[];
}

const SERVICE_COLORS: Record<string, string> = {
  CloudWatch: 'bg-blue-500',
  CloudTrail: 'bg-purple-500',
  ECS:        'bg-emerald-500',
  Lambda:     'bg-amber-500',
  EC2:        'bg-orange-500',
  RDS:        'bg-cyan-500',
  IAM:        'bg-red-500',
  Agent:      'bg-gray-500',
  Other:      'bg-gray-600',
};

function StatCard({
  label, value, sub, icon, accent = false,
}: { label: string; value: string | number; sub?: string; icon: React.ReactNode; accent?: boolean }) {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500 uppercase tracking-widest">{label}</span>
        <span className={cn('text-gray-500', accent && 'text-emerald-500')}>{icon}</span>
      </div>
      <div>
        <div className={cn('text-2xl font-bold', accent ? 'text-emerald-400' : 'text-gray-100')}>
          {value}
        </div>
        {sub && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [stats,   setStats]   = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    fetch('/stats')
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-500 text-sm gap-2">
        <div className="spinner-dots"><span /><span /><span /></div>
        Loading dashboard…
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex-1 flex items-center justify-center text-red-400 text-sm">
        Failed to load stats — is the backend running?
      </div>
    );
  }

  const { summary, activity, top_tools, service_breakdown, recent_sessions } = stats;
  const maxActivity = Math.max(...activity.map(d => d.sessions), 1);
  const errorRate = summary.total_tool_calls
    ? Math.round((summary.total_tool_errors / summary.total_tool_calls) * 100)
    : 0;

  return (
    <div className="flex-1 overflow-y-auto min-h-0">
      <div className="p-6 max-w-5xl mx-auto flex flex-col gap-6">

        {/* ── Stat cards ── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard
            label="Sessions"
            value={summary.total_sessions}
            icon={<MessageSquare size={15} />}
          />
          <StatCard
            label="Queries"
            value={summary.total_queries}
            sub={`${summary.total_sessions ? Math.round(summary.total_queries / summary.total_sessions * 10) / 10 : 0} avg / session`}
            icon={<MessageSquare size={15} />}
          />
          <StatCard
            label="Tool calls"
            value={summary.total_tool_calls.toLocaleString()}
            sub={errorRate > 0 ? `${errorRate}% error rate` : 'no errors'}
            icon={<Wrench size={15} />}
          />
          <StatCard
            label="Total cost"
            value={summary.total_cost_usd > 0 ? fmtCost(summary.total_cost_usd) : '$0'}
            sub={`${fmtTok(summary.total_input_tokens + summary.total_output_tokens)} tokens`}
            icon={<DollarSign size={15} />}
            accent
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

          {/* ── Activity chart ── */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <h2 className="text-xs text-gray-500 uppercase tracking-widest mb-4">
              Activity — last 14 days
            </h2>
            {activity.length === 0 ? (
              <p className="text-sm text-gray-600 py-6 text-center">No activity yet</p>
            ) : (
              <div className="flex items-end gap-1 h-20">
                {activity.map(d => (
                  <div key={d.date} className="flex-1 flex flex-col items-center gap-1 group relative">
                    <div
                      className="w-full bg-emerald-500/80 hover:bg-emerald-400 rounded-sm transition-colors"
                      style={{ height: `${Math.max((d.sessions / maxActivity) * 100, 8)}%` }}
                    />
                    <div className="absolute -top-6 left-1/2 -translate-x-1/2 hidden group-hover:block bg-gray-900 border border-gray-700 text-xs text-gray-300 px-1.5 py-0.5 rounded whitespace-nowrap z-10">
                      {d.date.slice(5)} · {d.sessions}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Service breakdown ── */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <h2 className="text-xs text-gray-500 uppercase tracking-widest mb-4">
              Calls by service
            </h2>
            {service_breakdown.length === 0 ? (
              <p className="text-sm text-gray-600 py-6 text-center">No tool calls yet</p>
            ) : (
              <div className="flex flex-col gap-2.5">
                {service_breakdown.map(s => (
                  <div key={s.service} className="flex items-center gap-3">
                    <span className="w-24 text-xs text-gray-400 shrink-0">{s.service}</span>
                    <div className="flex-1 bg-gray-700 rounded-full h-1.5">
                      <div
                        className={cn('h-1.5 rounded-full transition-all', SERVICE_COLORS[s.service] ?? 'bg-gray-500')}
                        style={{ width: `${s.pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-500 w-10 text-right shrink-0">{s.calls}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

          {/* ── Top tools ── */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <h2 className="text-xs text-gray-500 uppercase tracking-widest mb-3">Top tools</h2>
            {top_tools.length === 0 ? (
              <p className="text-sm text-gray-600 py-4 text-center">No tool calls yet</p>
            ) : (
              <div className="flex flex-col divide-y divide-gray-700/50">
                {top_tools.slice(0, 8).map(t => (
                  <div key={t.tool} className="flex items-center gap-3 py-2">
                    <span className="flex-1 font-mono text-xs text-amber-400 truncate">{t.tool}</span>
                    <span className="text-xs text-gray-400 tabular-nums">{t.count}</span>
                    {t.errors > 0 && (
                      <span className="flex items-center gap-0.5 text-[10px] text-red-400">
                        <AlertTriangle size={10} />{t.errors}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Recent sessions ── */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <h2 className="text-xs text-gray-500 uppercase tracking-widest mb-3">Recent sessions</h2>
            {recent_sessions.length === 0 ? (
              <p className="text-sm text-gray-600 py-4 text-center">No sessions yet</p>
            ) : (
              <div className="flex flex-col divide-y divide-gray-700/50">
                {recent_sessions.map(s => (
                  <Link
                    key={s.id}
                    to={`/chat/${s.id}`}
                    className="flex flex-col gap-0.5 py-2 hover:text-emerald-400 transition-colors group"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm text-gray-200 truncate group-hover:text-emerald-400 transition-colors">
                        {s.title ?? 'Untitled'}
                      </span>
                      <span className="text-xs text-gray-600 shrink-0 flex items-center gap-1">
                        <Clock size={10} />
                        {s.last_active_at ? relativeTime(s.last_active_at) : ''}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-gray-500">
                      <span>{s.query_count} quer{s.query_count === 1 ? 'y' : 'ies'}</span>
                      <span>{s.tool_count} tools</span>
                      {s.cost_usd > 0 && <span>{fmtCost(s.cost_usd)}</span>}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

        </div>

        {/* ── Token / latency footer ── */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Input tokens',  value: fmtTok(summary.total_input_tokens),  icon: <Zap size={13} /> },
            { label: 'Output tokens', value: fmtTok(summary.total_output_tokens), icon: <Zap size={13} /> },
            { label: 'Avg latency',   value: summary.avg_latency_ms ? `${(summary.avg_latency_ms / 1000).toFixed(1)}s` : '—', icon: <Clock size={13} /> },
          ].map(item => (
            <div key={item.label} className="bg-gray-800/50 border border-gray-700/60 rounded-lg px-4 py-3 flex items-center justify-between">
              <span className="text-xs text-gray-500">{item.label}</span>
              <div className="flex items-center gap-1.5 text-gray-300">
                <span className="text-gray-600">{item.icon}</span>
                <span className="text-sm font-mono font-medium">{item.value}</span>
              </div>
            </div>
          ))}
        </div>

      </div>
    </div>
  );
}
