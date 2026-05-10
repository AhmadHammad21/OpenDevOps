import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Clock, Send, MessageSquare, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';
import { fetchAlert } from '../lib/api';
import type { Alert } from '../types';

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
    const prompt = `Investigate this incident further:\n\nService: ${alert.service}\nError: ${alert.error}\nConfidence: ${alert.confidence}\nTime: ${alert.timestamp}\n\nPlease provide deeper root cause analysis, check related services, and suggest preventive measures.`;
    const sessionId = crypto.randomUUID();
    navigate(`/chat/${sessionId}?prompt=${encodeURIComponent(prompt)}`);
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
                alert.confidence === 'HIGH' ? 'bg-red-500' :
                alert.confidence === 'MEDIUM' ? 'bg-amber-500' : 'bg-gray-400'
              )} />
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{alert.service}</h1>
              <span className={cn(
                'text-xs font-bold px-2 py-0.5 rounded',
                alert.confidence === 'HIGH' ? 'bg-red-100 dark:bg-red-500/10 text-red-600 dark:text-red-400' :
                alert.confidence === 'MEDIUM' ? 'bg-amber-100 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400' :
                'bg-gray-100 dark:bg-[#27272A] text-gray-500 dark:text-[#71717A]'
              )}>{alert.confidence}</span>
            </div>
            <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-[#71717A]">
              <span className="flex items-center gap-1"><Clock size={12} /> {new Date(alert.timestamp).toLocaleString()}</span>
              {alert.sns_sent && (
                <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                  <Send size={12} /> SNS notified
                </span>
              )}
            </div>
          </div>
          <button onClick={investigate}
            className="flex items-center gap-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 px-4 py-2.5 rounded-lg transition-colors">
            <MessageSquare size={14} /> Investigate
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

      </div>
    </div>
  );
}
