import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Clock, MessageSquare, Loader2, CheckCircle2, XCircle, Radio } from 'lucide-react';
import { cn } from '../lib/utils';
import { fetchAlert } from '../lib/api';
import type { Alert, AlertNotification } from '../types';
import { IntegrationIcon } from '../components/icons/IntegrationIcon';

const CHANNEL_LABELS: Record<string, string> = {
  slack: 'Slack',
  sns: 'SNS',
  telegram: 'Telegram',
  email: 'Email',
  pagerduty: 'PagerDuty',
};

function NotificationRow({ n }: { n: AlertNotification }) {
  const label = CHANNEL_LABELS[n.channel] ?? n.channel;
  return (
    <div className="flex items-center gap-2.5">
      <IntegrationIcon name={n.channel} size={16} />
      <span className="text-[13px] text-gray-700 dark:text-[#CBD5E1] font-medium w-20">{label}</span>
      {n.status === 'delivered'
        ? <CheckCircle2 size={13} className="text-emerald-500" />
        : n.status === 'failed'
          ? <XCircle size={13} className="text-red-500" />
          : <Radio size={13} className="text-gray-400 dark:text-[#64748B]" />
      }
      <span className={cn(
        'text-[12px] font-medium',
        n.status === 'delivered' ? 'text-emerald-600 dark:text-emerald-400' :
        n.status === 'failed'    ? 'text-red-500 dark:text-red-400' :
                                   'text-gray-400 dark:text-[#64748B]'
      )}>
        {n.status}
      </span>
      {n.error && (
        <span className="text-[11px] text-red-400 truncate max-w-[200px]" title={n.error}>{n.error}</span>
      )}
    </div>
  );
}

export default function AlertDetailPage() {
  const { alertId } = useParams<{ alertId: string }>();
  const navigate = useNavigate();
  const [alert, setAlert] = useState<Alert | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!alertId) return;
    fetchAlert(alertId)
      .then(setAlert)
      .catch(() => navigate('/monitoring', { replace: true }))
      .finally(() => setLoading(false));
  }, [alertId, navigate]);

  const investigate = () => {
    if (!alert) return;
    if (alert.session_id) {
      navigate(`/chat/${alert.session_id}`);
    } else {
      const prompt = `Investigate this incident further:\n\nService: ${alert.service}\nError: ${alert.error}\nConfidence: ${alert.confidence}\nTime: ${alert.timestamp}\n\nPlease provide deeper root cause analysis, check related services, and suggest preventive measures.`;
      navigate(`/chat/${crypto.randomUUID()}?prompt=${encodeURIComponent(prompt)}`);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-gray-400" />
      </div>
    );
  }

  if (!alert) return null;

  return (
    <div className="flex-1 overflow-y-auto bg-white dark:bg-[#09090B]">
      <div className="max-w-3xl mx-auto px-6 py-8">

        <button onClick={() => navigate('/monitoring')}
          className="flex items-center gap-1.5 text-sm text-gray-500 dark:text-[#71717A] hover:text-gray-900 dark:hover:text-white mb-6 transition-colors">
          <ArrowLeft size={14} /> Back to Monitoring
        </button>

        <div className="flex items-start justify-between mb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className={cn(
                'w-3 h-3 rounded-full',
                alert.status === 'failed' ? 'bg-orange-500' :
                alert.confidence === 'HIGH' ? 'bg-red-500' :
                alert.confidence === 'MEDIUM' ? 'bg-amber-500' : 'bg-gray-400'
              )} />
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{alert.service}</h1>
              {alert.status === 'failed' ? (
                <span className="text-xs font-bold px-2 py-0.5 rounded bg-orange-100 dark:bg-orange-500/10 text-orange-600 dark:text-orange-400">
                  FAILED
                </span>
              ) : (
                <span className={cn(
                  'text-xs font-bold px-2 py-0.5 rounded',
                  alert.confidence === 'HIGH' ? 'bg-red-100 dark:bg-red-500/10 text-red-600 dark:text-red-400' :
                  alert.confidence === 'MEDIUM' ? 'bg-amber-100 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400' :
                  'bg-gray-100 dark:bg-[#27272A] text-gray-500 dark:text-[#71717A]'
                )}>{alert.confidence}</span>
              )}
            </div>
            <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-[#71717A]">
              <span className="flex items-center gap-1"><Clock size={12} /> {new Date(alert.timestamp.includes('Z') || alert.timestamp.includes('+') ? alert.timestamp : alert.timestamp + 'Z').toLocaleString()}</span>
              {alert.trigger_source && (
                <span className="flex items-center gap-1.5 text-[12px] font-medium px-2 py-0.5 rounded-full bg-gray-100 dark:bg-[#27272A] text-gray-600 dark:text-[#94A3B8]">
                  {alert.trigger_source === 'poller' ? '⏱ Poller' : '⚡ Event consumer'}
                </span>
              )}
            </div>
          </div>
          <button onClick={investigate}
            className="flex items-center gap-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 px-4 py-2.5 rounded-lg transition-colors">
            <MessageSquare size={14} /> {alert.session_id ? 'View investigation' : 'Investigate'}
          </button>
        </div>

        <section className="mb-6">
          <h2 className="text-xs font-semibold text-gray-500 dark:text-[#71717A] uppercase tracking-wider mb-2">Root Cause</h2>
          <div className="bg-red-50 dark:bg-red-500/5 border border-red-200 dark:border-red-500/20 rounded-xl p-4">
            <p className="text-sm text-gray-900 dark:text-white leading-relaxed">{alert.error}</p>
          </div>
        </section>

        {alert.resolution && (
          <section className="mb-6">
            <h2 className="text-xs font-semibold text-gray-500 dark:text-[#71717A] uppercase tracking-wider mb-2">Resolution</h2>
            <div className="bg-gray-50 dark:bg-[#18181B] border border-gray-200 dark:border-[#27272A] rounded-xl p-4">
              <p className="text-sm text-gray-700 dark:text-[#A1A1AA] whitespace-pre-line leading-relaxed">{alert.resolution}</p>
            </div>
          </section>
        )}

        {alert.notifications && alert.notifications.length > 0 && (
          <section className="mb-6">
            <h2 className="text-xs font-semibold text-gray-500 dark:text-[#71717A] uppercase tracking-wider mb-3">Notified via</h2>
            <div className="bg-gray-50 dark:bg-[#18181B] border border-gray-200 dark:border-[#27272A] rounded-xl px-4 py-3 space-y-2.5">
              {alert.notifications.map((n, i) => (
                <NotificationRow key={i} n={n} />
              ))}
            </div>
          </section>
        )}

      </div>
    </div>
  );
}
