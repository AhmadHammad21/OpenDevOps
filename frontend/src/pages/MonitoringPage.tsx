import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, CheckCircle, XCircle, AlertTriangle, RefreshCw, Radio, MessageSquare, ChevronRight, FlaskConical } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../lib/utils';
import { fetchAlerts, fetchServices, apiFetch } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import type { Alert, ServiceStatus } from '../types';

function timeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function buildPrompt(a: Alert): string {
  return `Investigate this incident further:\n\nService: ${a.service}\nError: ${a.error}\nConfidence: ${a.confidence}\nTime: ${a.timestamp}\n\nPlease provide deeper root cause analysis, check related services, and suggest preventive measures.`;
}

export default function MonitoringPage() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [services,       setServices]       = useState<ServiceStatus[]>([]);
  const [alerts,         setAlerts]         = useState<Alert[]>([]);
  const [loading,        setLoading]        = useState(true);
  const [testSending,    setTestSending]    = useState(false);
  const [infraEnabled,   setInfraEnabled]   = useState<boolean | null>(null);

  useEffect(() => {
    if (!isAdmin) return;
    apiFetch('/api/init/status')
      .then(r => r.json())
      .then(d => setInfraEnabled(!!d.event_infra_enabled))
      .catch(() => setInfraEnabled(false));
  }, [isAdmin]);

  const sendTestEvent = async () => {
    if (infraEnabled === false) {
      toast.error('Event monitoring not set up — go to Settings → AWS Configuration to enable it');
      return;
    }
    setTestSending(true);
    try {
      const r = await apiFetch('/api/init/test-event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'lambda' }),
      });
      if (!r.ok) {
        const d = await r.json();
        toast.error(d.detail || 'Failed to send test event');
        return;
      }
      toast.success('Test Lambda alarm sent — investigation will appear here in ~30s');
    } catch {
      toast.error('Failed to send test event');
    } finally {
      setTestSending(false);
    }
  };

  const load = () => {
    setLoading(true);
    Promise.all([fetchServices(), fetchAlerts()])
      .then(([s, a]) => { setServices(s); setAlerts(a); })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); const id = setInterval(load, 30000); return () => clearInterval(id); }, []);

  const healthy = services.filter(s => s.status === 'healthy').length;
  const errored = services.filter(s => s.status === 'error').length;
  const emptyTitle = infraEnabled === false ? 'Event monitoring is not enabled' : 'No activity yet';
  const emptyCopy = infraEnabled === false
    ? 'Enable event monitoring in Settings, or turn on proactive polling, to populate this feed.'
    : 'Listening for AWS events. Incidents will appear here when detected.';

  const investigate = (a: Alert) => {
    if (a.session_id) {
      navigate(`/chat/${a.session_id}`);
    } else {
      const sessionId = crypto.randomUUID();
      navigate(`/chat/${sessionId}?prompt=${encodeURIComponent(buildPrompt(a))}`);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-white dark:bg-[#09090B]">
      <div className="max-w-4xl mx-auto px-6 py-8">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white tracking-tight">Monitoring</h1>
            <p className="text-sm text-gray-500 dark:text-[#71717A] mt-1">Real-time incidents and service health</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 px-2.5 py-1 rounded-full">
              <Radio size={10} className={loading ? 'animate-pulse' : ''} />
              <span className="font-medium">{infraEnabled === false ? 'Feed' : 'Live'}</span>
            </div>
            {isAdmin && (
              <button
                onClick={sendTestEvent}
                disabled={testSending || infraEnabled === false}
                title={infraEnabled === false ? 'Event monitoring not configured' : 'Send a synthetic Lambda alarm to test the pipeline'}
                className="flex items-center gap-1.5 text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 px-3 py-1.5 border border-indigo-200 dark:border-indigo-500/30 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-500/10 disabled:opacity-50 transition-colors"
              >
                <FlaskConical size={13} className={testSending ? 'animate-spin' : ''} />
                <span className="hidden sm:inline">Test event</span>
              </button>
            )}
            <button onClick={load}
              className="flex items-center gap-1.5 text-sm font-medium text-gray-600 dark:text-[#A1A1AA] hover:text-gray-900 dark:hover:text-white px-3 py-1.5 border border-gray-200 dark:border-[#27272A] rounded-lg hover:bg-gray-50 dark:hover:bg-[#18181B] transition-colors">
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {/* Service Health */}
        {services.length > 0 && (
          <section className="mb-8">
            <div className="flex items-center gap-4 mb-3">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white uppercase tracking-wider">Services</h2>
              {healthy > 0 && <span className="text-xs text-emerald-600 dark:text-emerald-400">{healthy} healthy</span>}
              {errored > 0 && <span className="text-xs text-red-500">{errored} failing</span>}
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 gap-2">
              {services.map(s => (
                <div key={s.name} className={cn(
                  'rounded-lg border px-3 py-2.5',
                  s.status === 'healthy' ? 'border-emerald-200 dark:border-emerald-500/20 bg-emerald-50/50 dark:bg-emerald-500/5' :
                  s.status === 'error' ? 'border-red-200 dark:border-red-500/20 bg-red-50/50 dark:bg-red-500/5' :
                  'border-amber-200 dark:border-amber-500/20 bg-amber-50/50 dark:bg-amber-500/5'
                )}>
                  <div className="flex items-center gap-1.5">
                    {s.status === 'healthy' ? <CheckCircle size={12} className="text-emerald-500" /> :
                     s.status === 'error' ? <XCircle size={12} className="text-red-500" /> :
                     <AlertTriangle size={12} className="text-amber-500" />}
                    <span className="text-xs font-semibold text-gray-900 dark:text-white truncate">{s.name}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Empty state */}
        {services.length === 0 && alerts.length === 0 && !loading && (
          <div className="text-center py-20">
            <div className="w-14 h-14 bg-gray-100 dark:bg-[#18181B] rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Activity size={24} className="text-gray-400 dark:text-[#52525B]" />
            </div>
            <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-1">{emptyTitle}</h2>
            <p className="text-sm text-gray-500 dark:text-[#71717A] max-w-xs mx-auto">
              {emptyCopy}
            </p>
          </div>
        )}

        {/* Incidents */}
        {alerts.length > 0 && (
          <section>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white uppercase tracking-wider">Incidents</h2>
              <span className="text-xs text-gray-400 dark:text-[#52525B]">{alerts.length} total</span>
            </div>

            <div className="space-y-2">
              {alerts.map(a => (
                <div key={a.id}
                  onClick={() => navigate(`/monitoring/${a.id}`)}
                  className="group rounded-xl border border-gray-200 dark:border-[#27272A] bg-white dark:bg-[#18181B] p-4 cursor-pointer transition-all hover:border-gray-300 dark:hover:border-[#3F3F46] hover:shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      'w-2.5 h-2.5 rounded-full shrink-0',
                      a.status === 'failed' ? 'bg-orange-500' :
                      a.confidence === 'HIGH' ? 'bg-red-500' :
                      a.confidence === 'MEDIUM' ? 'bg-amber-500' : 'bg-gray-400'
                    )} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-gray-900 dark:text-white">{a.service}</span>
                        {a.status === 'failed' ? (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-orange-100 dark:bg-orange-500/10 text-orange-600 dark:text-orange-400">
                            FAILED
                          </span>
                        ) : (
                          <span className={cn(
                            'text-[10px] font-bold px-1.5 py-0.5 rounded',
                            a.confidence === 'HIGH' ? 'bg-red-100 dark:bg-red-500/10 text-red-600 dark:text-red-400' :
                            a.confidence === 'MEDIUM' ? 'bg-amber-100 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400' :
                            'bg-gray-100 dark:bg-[#27272A] text-gray-500 dark:text-[#71717A]'
                          )}>{a.confidence}</span>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 dark:text-[#A1A1AA] truncate mt-0.5">{a.error}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-gray-400 dark:text-[#52525B]">{timeAgo(a.timestamp)}</span>
                      <button
                        onClick={e => { e.stopPropagation(); investigate(a); }}
                        className="hidden group-hover:flex items-center gap-1 text-xs font-medium text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 px-2 py-1 rounded-md hover:bg-indigo-100 dark:hover:bg-indigo-500/20 transition-colors"
                      >
                        <MessageSquare size={11} /> {a.session_id ? 'View investigation' : 'Investigate'}
                      </button>
                      <ChevronRight size={14} className="text-gray-300 dark:text-[#3F3F46] group-hover:text-gray-500 dark:group-hover:text-[#71717A] transition-colors" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

      </div>
    </div>
  );
}
