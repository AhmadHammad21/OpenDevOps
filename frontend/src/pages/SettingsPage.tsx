import { useState, useEffect } from 'react';
import { ExternalLink, Eye, EyeOff, Key } from 'lucide-react';
import { apiFetch } from '../lib/api';

interface EnvVar  { key: string; value: string; secret: boolean }
interface AgentVar { key: string; label: string; value: string; hint: string }
interface SettingsData { env: EnvVar[]; agent: AgentVar[] }

type Tab = 'env' | 'agent' | 'integrations';

const TABS: { id: Tab; label: string }[] = [
  { id: 'env',          label: 'Environment' },
  { id: 'agent',        label: 'Agent config' },
  { id: 'integrations', label: 'Integrations' },
];

const INTEGRATIONS = [
  { name: 'GitHub',    desc: 'Connect your repositories',  connected: false },
  { name: 'Slack',     desc: 'Get incident notifications', connected: false },
  { name: 'PagerDuty', desc: 'Alert on failures',          connected: false },
  { name: 'Datadog',   desc: 'Send metrics and traces',    connected: false },
];

export default function SettingsPage() {
  const [tab, setTab]     = useState<Tab>('env');
  const [shown, setShown] = useState<Record<string, boolean>>({});
  const [data, setData]   = useState<SettingsData | null>(null);

  useEffect(() => {
    apiFetch('/settings')
      .then(r => r.json())
      .then(d => setData(d as SettingsData))
      .catch(() => { /* silently ignore — show nothing */ });
  }, []);

  const toggleShow = (k: string) => setShown(p => ({ ...p, [k]: !p[k] }));

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50 dark:bg-[#0F0F12] min-h-0">
      <div className="bg-white dark:bg-[#18181C] border-b border-gray-200 dark:border-[#27272F] px-7 py-[14px]">
        <div className="text-[16px] font-bold text-gray-900 dark:text-[#F1F5F9] tracking-[-0.02em]">Settings</div>
        <div className="text-[13px] text-gray-500 dark:text-[#94A3B8] mt-0.5">Read-only view of your agent configuration. Edit values in your <code className="font-mono text-[12px] bg-gray-100 dark:bg-[#27272F] px-1 rounded">.env</code> file and restart the server to apply changes.</div>
      </div>

      <div className="flex bg-white dark:bg-[#18181C] border-b border-gray-200 dark:border-[#27272F] px-7">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-3.5 py-2.5 text-[13px] font-medium transition-colors border-b-2 -mb-px ${
              tab === t.id
                ? 'text-indigo-500 dark:text-[#818CF8] border-indigo-500 dark:border-[#818CF8]'
                : 'text-gray-500 dark:text-[#94A3B8] border-transparent hover:text-gray-700 dark:hover:text-[#F1F5F9]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="px-7 py-6 max-w-[760px]">

        {tab === 'env' && (
          <div className="bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
            <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#27272F] bg-gray-50 dark:bg-[#1E1E24]">
              <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Environment Variables</span>
            </div>
            <div className="flex px-4 py-[7px] bg-gray-50 dark:bg-[#1E1E24] border-b border-gray-200 dark:border-[#27272F]">
              <span className="text-[10px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em] flex-[0_0_220px]">Key</span>
              <span className="text-[10px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em] flex-1">Value</span>
            </div>
            {data ? data.env.map((v, i) => (
              <div key={v.key} className={`flex items-center gap-2 px-4 py-[9px] ${i < data.env.length - 1 ? 'border-b border-gray-200 dark:border-[#27272F]' : ''}`}>
                <div className="flex-[0_0_220px] flex items-center gap-1.5">
                  {v.secret && <Key size={11} className="text-gray-400 dark:text-[#64748B] shrink-0" />}
                  <span className="font-mono text-[12px] font-medium text-gray-700 dark:text-[#CBD5E1]">{v.key}</span>
                </div>
                <div className="flex-1 font-mono text-[12px] text-gray-500 dark:text-[#94A3B8] overflow-hidden text-ellipsis whitespace-nowrap">
                  {v.secret && !shown[v.key] ? '••••••••••••' : v.value}
                </div>
                {v.secret && (
                  <button onClick={() => toggleShow(v.key)} className="p-[3px] rounded hover:bg-gray-100 dark:hover:bg-[#27272F] text-gray-400 dark:text-[#64748B] hover:text-gray-600 dark:hover:text-[#94A3B8] transition-colors">
                    {shown[v.key] ? <EyeOff size={13} /> : <Eye size={13} />}
                  </button>
                )}
              </div>
            )) : (
              <div className="px-4 py-6 text-[13px] text-gray-400 dark:text-[#64748B] text-center">Loading…</div>
            )}
          </div>
        )}

        {tab === 'agent' && (
          <div className="bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
            <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#27272F] bg-gray-50 dark:bg-[#1E1E24]">
              <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Agent Configuration</span>
            </div>
            {data ? data.agent.map((f, i) => (
              <div key={f.key} className={`flex items-center gap-4 px-4 py-[11px] ${i < data.agent.length - 1 ? 'border-b border-gray-200 dark:border-[#27272F]' : ''}`}>
                <div className="flex-[0_0_220px]">
                  <div className="text-[12px] font-medium text-gray-700 dark:text-[#CBD5E1]">{f.label}</div>
                  <div className="text-[11px] text-gray-400 dark:text-[#64748B] mt-0.5">{f.hint}</div>
                </div>
                <span className="font-mono text-[13px] font-medium text-gray-900 dark:text-[#F1F5F9]">{f.value}</span>
              </div>
            )) : (
              <div className="px-4 py-6 text-[13px] text-gray-400 dark:text-[#64748B] text-center">Loading…</div>
            )}
          </div>
        )}

        {tab === 'integrations' && (
          <>
            <div className="bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)] mb-4">
              {INTEGRATIONS.map((intg, i) => (
                <div key={i} className={`flex items-center gap-3 px-[18px] py-[14px] ${i < INTEGRATIONS.length - 1 ? 'border-b border-gray-200 dark:border-[#27272F]' : ''}`}>
                  <div className="w-[34px] h-[34px] bg-gray-100 dark:bg-[#27272F] rounded-lg flex items-center justify-center shrink-0">
                    <span className="text-sm">{intg.name === 'Slack' ? '💬' : intg.name === 'GitHub' ? '🐱' : intg.name === 'PagerDuty' ? '📟' : '📊'}</span>
                  </div>
                  <div className="flex-1">
                    <div className="text-[13px] font-medium text-gray-900 dark:text-[#F1F5F9]">{intg.name}</div>
                    <div className="text-[12px] text-gray-500 dark:text-[#94A3B8]">{intg.desc}</div>
                  </div>
                  <button className="text-[12px] font-medium text-gray-600 dark:text-[#94A3B8] bg-white dark:bg-[#18181C] hover:bg-gray-50 dark:hover:bg-[#27272F] border border-gray-300 dark:border-[#3F3F47] rounded-[5px] px-2.5 py-[5px] shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-colors">
                    Connect
                  </button>
                </div>
              ))}
            </div>
            <a href="https://openrouter.ai/models" target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-[13px] text-indigo-500 dark:text-[#818CF8] hover:text-indigo-600 dark:hover:text-[#6366F1] transition-colors">
              Browse available models on OpenRouter <ExternalLink size={13} />
            </a>
          </>
        )}
      </div>
    </div>
  );
}
