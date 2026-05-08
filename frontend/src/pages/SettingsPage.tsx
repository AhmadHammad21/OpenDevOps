import { useState } from 'react';
import { ExternalLink, Eye, EyeOff, Key, Trash2, Plus, Check } from 'lucide-react';

const ENV_VARS = [
  { key: 'LLM_MODEL',      value: 'openrouter/anthropic/claude-3.5-sonnet', secret: false },
  { key: 'LLM_API_KEY',    value: 'sk-or-v1-••••••••4f2a',                  secret: true  },
  { key: 'AWS_REGION',     value: 'us-east-1',                               secret: false },
  { key: 'AWS_PROFILE',    value: 'devops-agent-readonly',                   secret: false },
  { key: 'MAX_TOOL_CALLS', value: '20',                                      secret: false },
  { key: 'DATABASE_URL',   value: 'postgres://prod.cluster.internal',        secret: true  },
  { key: 'LOG_LEVEL',      value: 'INFO',                                    secret: false },
];

const INTEGRATIONS = [
  { name: 'GitHub',    desc: 'Connect your repositories',  connected: false },
  { name: 'Slack',     desc: 'Get incident notifications', connected: false },
  { name: 'PagerDuty', desc: 'Alert on failures',          connected: false },
  { name: 'Datadog',   desc: 'Send metrics and traces',    connected: false },
];

const AGENT_FIELDS = [
  { label: 'Default region', value: 'us-east-1', hint: 'AWS region for tool calls' },
  { label: 'Max tool calls', value: '20',         hint: 'Hard cap per investigation run' },
];

type Tab = 'env' | 'agent' | 'integrations';

const TABS: { id: Tab; label: string }[] = [
  { id: 'env',          label: 'Environment' },
  { id: 'agent',        label: 'Agent config' },
  { id: 'integrations', label: 'Integrations' },
];

export default function SettingsPage() {
  const [tab, setTab]   = useState<Tab>('env');
  const [shown, setShown] = useState<Record<string, boolean>>({});
  const [saved, setSaved] = useState(false);

  const toggleShow = (k: string) => setShown(p => ({ ...p, [k]: !p[k] }));
  const handleSave = () => { setSaved(true); setTimeout(() => setSaved(false), 2000); };

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50 dark:bg-[#0F0F12] min-h-0">
      <div className="bg-white dark:bg-[#18181C] border-b border-gray-200 dark:border-[#27272F] px-7 py-[14px]">
        <div className="text-[16px] font-bold text-gray-900 dark:text-[#F1F5F9] tracking-[-0.02em]">Settings</div>
        <div className="text-[13px] text-gray-500 dark:text-[#94A3B8] mt-0.5">Manage your agent configuration and environment</div>
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
          <>
            <div className="bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)] mb-3.5">
              <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#27272F] flex items-center justify-between bg-gray-50 dark:bg-[#1E1E24]">
                <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Environment Variables</span>
                <button className="flex items-center gap-1.5 text-[12px] font-medium text-gray-500 dark:text-[#94A3B8] hover:text-gray-700 dark:hover:text-[#F1F5F9] px-2.5 py-[5px] border border-gray-300 dark:border-[#3F3F47] rounded-[5px] bg-white dark:bg-[#18181C] shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-colors">
                  <Plus size={12} /> Add variable
                </button>
              </div>
              <div className="flex px-4 py-[7px] bg-gray-50 dark:bg-[#1E1E24] border-b border-gray-200 dark:border-[#27272F]">
                <span className="text-[10px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em] flex-[0_0_200px]">Key</span>
                <span className="text-[10px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em] flex-1">Value</span>
              </div>
              {ENV_VARS.map((v, i) => (
                <div key={v.key} className={`flex items-center gap-2 px-4 py-[9px] ${i < ENV_VARS.length - 1 ? 'border-b border-gray-200 dark:border-[#27272F]' : ''}`}>
                  <div className="flex-[0_0_200px] flex items-center gap-1.5">
                    {v.secret && <Key size={11} className="text-gray-400 dark:text-[#64748B] shrink-0" />}
                    <span className="font-mono text-[12px] font-medium text-gray-700 dark:text-[#CBD5E1]">{v.key}</span>
                  </div>
                  <div className="flex-1 font-mono text-[12px] text-gray-500 dark:text-[#94A3B8] overflow-hidden text-ellipsis whitespace-nowrap">
                    {v.secret && !shown[v.key] ? '••••••••••••' : v.value}
                  </div>
                  <div className="flex gap-0.5">
                    {v.secret && (
                      <button onClick={() => toggleShow(v.key)} className="p-[3px] rounded hover:bg-gray-100 dark:hover:bg-[#27272F] text-gray-400 dark:text-[#64748B] hover:text-gray-600 dark:hover:text-[#94A3B8] transition-colors">
                        {shown[v.key] ? <EyeOff size={13} /> : <Eye size={13} />}
                      </button>
                    )}
                    <button className="p-[3px] rounded hover:bg-gray-100 dark:hover:bg-[#27272F] text-gray-400 dark:text-[#64748B] hover:text-red-500 dark:hover:text-[#F87171] transition-colors">
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex justify-end gap-2">
              <button className="text-[13px] font-medium text-gray-500 dark:text-[#94A3B8] hover:text-gray-700 dark:hover:text-[#F1F5F9] px-3.5 py-[7px] rounded-[6px] transition-colors">Discard</button>
              <button onClick={handleSave} className="flex items-center gap-1.5 text-[13px] font-medium text-white bg-indigo-500 dark:bg-[#818CF8] hover:bg-indigo-600 dark:hover:bg-[#6366F1] px-3.5 py-[7px] rounded-[6px] transition-colors shadow-[0_1px_2px_rgba(99,102,241,0.25)]">
                {saved ? <><Check size={13} /> Saved!</> : 'Save changes'}
              </button>
            </div>
          </>
        )}

        {tab === 'agent' && (
          <div className="bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-lg p-5 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
            {AGENT_FIELDS.map((f, i) => (
              <div key={i} className="mb-4 last:mb-0">
                <label className="block text-[12px] font-medium text-gray-700 dark:text-[#CBD5E1] mb-[5px]">{f.label}</label>
                <input defaultValue={f.value}
                  className="w-full font-sans text-[13px] text-gray-900 dark:text-[#F1F5F9] bg-white dark:bg-[#18181C] border border-gray-300 dark:border-[#3F3F47] rounded-[6px] px-2.5 py-[7px] outline-none focus:border-indigo-500 dark:focus:border-[#818CF8] focus:shadow-[0_0_0_3px_rgba(99,102,241,0.12)] dark:focus:shadow-[0_0_0_3px_rgba(129,140,248,0.12)] transition-all" />
                <div className="text-[11px] text-gray-400 dark:text-[#64748B] mt-1">{f.hint}</div>
              </div>
            ))}
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
                  {intg.connected ? (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-[#34D399] bg-emerald-50 dark:bg-[#0D2B1D] border border-emerald-200 dark:border-[#1A4A30] rounded px-1.5 py-[2px]">
                      <span className="w-[5px] h-[5px] rounded-full bg-emerald-500 dark:bg-[#34D399]" /> Connected
                    </span>
                  ) : (
                    <button className="text-[12px] font-medium text-gray-600 dark:text-[#94A3B8] bg-white dark:bg-[#18181C] hover:bg-gray-50 dark:hover:bg-[#27272F] border border-gray-300 dark:border-[#3F3F47] rounded-[5px] px-2.5 py-[5px] shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-colors">
                      Connect
                    </button>
                  )}
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
