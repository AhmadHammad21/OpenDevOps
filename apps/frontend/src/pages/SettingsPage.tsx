import { useState, useEffect } from 'react';
import { ExternalLink, Eye, EyeOff, Key, CheckCircle, XCircle, AlertTriangle, Loader2, Shield, Radio, Trash2, Zap, Send } from 'lucide-react';
import { SlackIcon, TelegramIcon, IntegrationIcon } from '../components/icons/IntegrationIcon';
import { toast } from 'sonner';
import { apiFetch } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { cn } from '../lib/utils';
import LlmBackendCard from '../components/LlmBackendCard';
import type { LlmBackendInfo, LlmSettings } from '../types';

interface EnvVar   { key: string; value: string; secret: boolean }
interface AgentVar { key: string; label: string; value: string; hint: string }
interface SettingsData { env: EnvVar[]; agent: AgentVar[]; llm_backend?: LlmBackendInfo }
interface PermResult   { passed: boolean | null; error: string | null }

type Tab = 'env' | 'agent' | 'integrations' | 'aws' | 'preferences';

const SVC: Record<string, { label: string; desc: string }> = {
  cloudwatch: { label: 'CloudWatch',  desc: 'Alarms, metrics, logs' },
  cloudtrail: { label: 'CloudTrail',  desc: 'API event history' },
  ecs:        { label: 'ECS',         desc: 'Container services' },
  lambda:     { label: 'Lambda',      desc: 'Serverless functions' },
  ec2:        { label: 'EC2',         desc: 'Instance status' },
  rds:        { label: 'RDS',         desc: 'Database events' },
  iam:        { label: 'IAM / STS',   desc: 'Identity & access' },
  sns:        { label: 'SNS',         desc: 'Alert publishing' },
  sqs:        { label: 'SQS',         desc: 'Event queue' },
  events:     { label: 'EventBridge', desc: 'Event rules' },
};

const COMING_SOON_INTEGRATIONS = [
  { name: 'GitHub',    desc: 'Connect your repositories', iconKey: 'github' },
  { name: 'PagerDuty', desc: 'Alert on failures',         iconKey: 'pagerduty' },
  { name: 'Datadog',   desc: 'Send metrics and traces',   iconKey: 'datadog' },
];

const inputCls = 'w-full font-mono text-[12px] text-gray-700 dark:text-[#CBD5E1] bg-white dark:bg-[#000000] border border-gray-200 dark:border-[#1E222B] rounded-md px-3 py-1.5 outline-none focus:border-indigo-500 dark:focus:border-[#00A3FF] focus:ring-1 focus:ring-indigo-500/20 dark:focus:ring-[#00A3FF]/20 transition-all placeholder:text-gray-300 dark:placeholder:text-[#2A2F3A]';

export default function SettingsPage() {
  const { isAdmin }   = useAuth();
  const { theme, toggle } = useTheme();
  const [tab, setTab] = useState<Tab>(isAdmin ? 'aws' : 'env');
  const [shown, setShown] = useState<Record<string, boolean>>({});
  const [data, setData]   = useState<SettingsData | null>(null);

  // Integrations tab state
  const [slackConfigured,    setSlackConfigured]    = useState(false);
  const [slackTesting,       setSlackTesting]       = useState(false);
  const [telegramConfigured, setTelegramConfigured] = useState(false);
  const [telegramTesting,    setTelegramTesting]    = useState(false);

  // AWS tab state
  const [sqsUrl,        setSqsUrl]        = useState('');
  const [awsRegion,     setAwsRegion]     = useState('');
  const [awsSaving,     setAwsSaving]     = useState(false);
  const [awsChecking,   setAwsChecking]   = useState(false);
  const [perms,         setPerms]         = useState<Record<string, PermResult>>({});
  // Event monitoring section
  const [infraEnabled,  setInfraEnabled]  = useState(false);
  const [infraRules,    setInfraRules]    = useState<Record<string, string>>({});
  const [infraBusy,     setInfraBusy]     = useState(false);

  // LLM picker (Agent config tab)
  const [llm,           setLlm]           = useState<LlmSettings | null>(null);
  const [llmSource,     setLlmSource]     = useState<string>('');
  const [llmModel,      setLlmModel]      = useState<string>('');
  const [llmSaving,     setLlmSaving]     = useState(false);
  // When true, the model field becomes free-text so the user can type a model name
  // we haven't curated yet (a new release, a niche OpenRouter variant, an Ollama tag).
  const [llmCustomMode, setLlmCustomMode] = useState(false);
  const _CUSTOM = '__custom__';

  const TABS: { id: Tab; label: string }[] = [
    ...(isAdmin ? [{ id: 'aws' as Tab, label: 'AWS Configuration' }] : []),
    { id: 'env',          label: 'Environment' },
    { id: 'agent',        label: 'Agent config' },
    { id: 'integrations', label: 'Integrations' },
    { id: 'preferences',  label: 'Preferences' },
  ];

  useEffect(() => {
    apiFetch('/api/settings')
      .then(r => r.json())
      .then(d => {
        const sd = d as SettingsData;
        setData(sd);
        const slackEnv = sd.env.find(e => e.key === 'SLACK_WEBHOOK_URL');
        setSlackConfigured(!!slackEnv && slackEnv.value !== '(not set)');
        const tgToken = sd.env.find(e => e.key === 'TELEGRAM_BOT_TOKEN');
        const tgChat  = sd.env.find(e => e.key === 'TELEGRAM_CHAT_ID');
        setTelegramConfigured(
          !!tgToken && tgToken.value !== '(not set)' &&
          !!tgChat  && tgChat.value  !== '(not set)'
        );
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (tab !== 'aws') return;
    apiFetch('/api/init/status')
      .then(r => r.json())
      .then(d => {
        setSqsUrl(d.sqs_queue_url || '');
        setAwsRegion(d.aws_region || '');
        setInfraEnabled(!!d.event_infra_enabled);
        setInfraRules(d.eventbridge_rule_arns || {});
      })
      .catch(() => {});
  }, [tab]);

  useEffect(() => {
    if (tab !== 'agent') return;
    apiFetch('/api/settings/llm')
      .then(r => r.json())
      .then((d: LlmSettings) => {
        setLlm(d);
        const src = d.current.source || d.backend.source || '';
        const mdl = d.current.model || d.backend.model || '';
        setLlmSource(src);
        setLlmModel(mdl);
        // If the saved model isn't in the provider's curated list, treat it as custom.
        const provider = d.providers.find(p => p.name === src);
        if (mdl && provider && !provider.models.includes(mdl)) {
          setLlmCustomMode(true);
        }
      })
      .catch(() => {});
  }, [tab]);

  const selectedProvider = llm?.providers.find(p => p.name === llmSource) || null;
  const availableModelsForSource = selectedProvider?.models || [];

  // Hint for the custom-model text input: prefix the provider expects (anthropic/, openrouter/, …).
  // Used as placeholder so users don't have to remember the LiteLLM naming convention.
  const customModelHint = (() => {
    if (!llmSource) return 'provider/model-name';
    if (llmSource === 'claude_code') return 'anthropic/claude-…';
    return `${llmSource}/your-model-name`;
  })();

  const onSelectProvider = (name: string) => {
    setLlmSource(name);
    setLlmCustomMode(false);
    const p = llm?.providers.find(pr => pr.name === name);
    setLlmModel(p?.models[0] || '');
  };

  const onSelectModel = (value: string) => {
    if (value === _CUSTOM) {
      setLlmCustomMode(true);
      setLlmModel('');
    } else {
      setLlmCustomMode(false);
      setLlmModel(value);
    }
  };

  const saveLlmPick = async () => {
    setLlmSaving(true);
    try {
      const r = await apiFetch('/api/settings/llm', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: llmSource, model: llmModel }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => null);
        throw new Error(err?.detail || 'Save failed');
      }
      toast.success('LLM updated — new chats will use it');
      // Refresh the backend info so the active-model card reflects the new pick.
      apiFetch('/api/settings').then(r => r.json()).then(d => setData(d as SettingsData)).catch(() => {});
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Failed to save');
    } finally {
      setLlmSaving(false);
    }
  };

  const toggleShow = (k: string) => setShown(p => ({ ...p, [k]: !p[k] }));

  const saveAwsConfig = async () => {
    setAwsSaving(true);
    try {
      const r = await apiFetch('/api/init/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sqs_queue_url: sqsUrl, aws_region: awsRegion }),
      });
      if (!r.ok) throw new Error('save failed');
      toast.success('AWS configuration saved');
    } catch {
      toast.error('Failed to save configuration');
    } finally {
      setAwsSaving(false);
    }
  };

  const checkPerms = async () => {
    setAwsChecking(true);
    try {
      const r = await apiFetch('/api/init/check-permissions', { method: 'POST' });
      const d = await r.json() as { permissions: Record<string, PermResult> };
      setPerms(d.permissions);
    } catch {
      toast.error('Permission check failed');
    } finally {
      setAwsChecking(false);
    }
  };

  const createInfra = async () => {
    setInfraBusy(true);
    try {
      const r = await apiFetch('/api/init/complete', { method: 'POST' });
      const d = await r.json() as { initialized: boolean; event_infra_enabled?: boolean; error?: string | null; detail?: string };
      if (!r.ok || !d.event_infra_enabled) { toast.error(d.error || d.detail || 'Infrastructure setup failed'); return; }
      toast.success('Event monitoring enabled');
      // Refresh status
      const s = await apiFetch('/api/init/status').then(res => res.json());
      setInfraEnabled(true);
      setSqsUrl(s.sqs_queue_url || '');
      setInfraRules(s.eventbridge_rule_arns || {});
    } catch {
      toast.error('Failed to create infrastructure');
    } finally {
      setInfraBusy(false);
    }
  };

  const teardownInfra = async () => {
    if (!window.confirm('Remove SQS queue and EventBridge rules? This will stop all automatic incident detection.')) return;
    setInfraBusy(true);
    try {
      const r = await apiFetch('/api/init/infra', { method: 'DELETE' });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail?.errors?.join('\n') || d.detail || 'Teardown failed');
      }
      toast.success('Event monitoring disabled');
      setInfraEnabled(false);
      setInfraRules({});
      setSqsUrl('');
    } catch (err) {
      toast.error((err as Error).message || 'Teardown failed');
    } finally {
      setInfraBusy(false);
    }
  };

  const testSlack = async () => {
    setSlackTesting(true);
    try {
      const r = await apiFetch('/api/integrations/slack/test', { method: 'POST' });
      if (!r.ok) throw new Error('Request failed');
      toast.success('Test message sent to Slack');
    } catch {
      toast.error('Failed to send test message');
    } finally {
      setSlackTesting(false);
    }
  };

  const testTelegram = async () => {
    setTelegramTesting(true);
    try {
      const r = await apiFetch('/api/integrations/telegram/test', { method: 'POST' });
      if (!r.ok) throw new Error('Request failed');
      toast.success('Test message sent to Telegram');
    } catch {
      toast.error('Failed to send test message');
    } finally {
      setTelegramTesting(false);
    }
  };

  const passed = Object.values(perms).filter(r => r.passed).length;
  const total  = Object.keys(perms).length;

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50 dark:bg-[#000000] min-h-0">
      <div className="bg-white dark:bg-[#0A0C10] border-b border-gray-200 dark:border-[#1E222B] px-7 py-[14px]">
        <div className="text-[16px] font-bold text-gray-900 dark:text-[#E4E1EA] tracking-[-0.02em]">Settings</div>
        <div className="text-[13px] text-gray-500 dark:text-[#94A3B8] mt-0.5">
          View your agent configuration. Edit <code className="font-mono text-[12px] bg-gray-100 dark:bg-[#1E222B] px-1 rounded">.env</code> and restart to apply environment changes.
        </div>
      </div>

      <div className="flex bg-white dark:bg-[#0A0C10] border-b border-gray-200 dark:border-[#1E222B] px-7">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-3.5 py-2.5 text-[14px] font-medium transition-colors border-b-2 -mb-px ${
              tab === t.id
                ? 'text-indigo-500 dark:text-[#00A3FF] border-indigo-500 dark:border-[#00A3FF]'
                : 'text-gray-500 dark:text-[#94A3B8] border-transparent hover:text-gray-700 dark:hover:text-[#E4E1EA]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="px-7 py-6 max-w-[760px]">

        {/* Environment tab */}
        {tab === 'env' && (
          <>
          {data?.llm_backend && (
            <div className="mb-5">
              <p className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em] mb-2">LLM Backend</p>
              <LlmBackendCard backend={data.llm_backend} />
            </div>
          )}
          <div className="bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
            <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#1E222B] bg-gray-50 dark:bg-[#15181F]">
              <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Environment Variables</span>
            </div>
            <div className="flex px-4 py-[7px] bg-gray-50 dark:bg-[#15181F] border-b border-gray-200 dark:border-[#1E222B]">
              <span className="text-[10px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em] flex-[0_0_220px]">Key</span>
              <span className="text-[10px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em] flex-1">Value</span>
            </div>
            {data ? data.env.map((v, i) => (
              <div key={v.key} className={`flex items-center gap-2 px-4 py-[9px] ${i < data.env.length - 1 ? 'border-b border-gray-200 dark:border-[#1E222B]' : ''}`}>
                <div className="flex-[0_0_220px] flex items-center gap-1.5">
                  {v.secret && <Key size={11} className="text-gray-400 dark:text-[#64748B] shrink-0" />}
                  <span className="font-mono text-[13px] font-medium text-gray-700 dark:text-[#CBD5E1]">{v.key}</span>
                </div>
                <div className="flex-1 font-mono text-[13px] text-gray-500 dark:text-[#94A3B8] overflow-hidden text-ellipsis whitespace-nowrap">
                  {v.secret && !shown[v.key] ? '••••••••••••' : v.value}
                </div>
                {v.secret && (
                  <button onClick={() => toggleShow(v.key)} className="p-[3px] rounded hover:bg-gray-100 dark:hover:bg-[#1E222B] text-gray-400 dark:text-[#64748B] hover:text-gray-600 dark:hover:text-[#94A3B8] transition-colors">
                    {shown[v.key] ? <EyeOff size={13} /> : <Eye size={13} />}
                  </button>
                )}
              </div>
            )) : (
              <div className="px-4 py-6 text-[13px] text-gray-400 dark:text-[#64748B] text-center">Loading…</div>
            )}
          </div>
          </>
        )}

        {/* Agent config tab */}
        {tab === 'agent' && (
          <div className="space-y-4">
            {/* LLM picker card */}
            <div className="bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#1E222B] bg-gray-50 dark:bg-[#15181F] flex items-center justify-between">
                <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">LLM</span>
                {data?.llm_backend && (
                  <span className="text-[11px] font-mono text-gray-500 dark:text-[#94A3B8]">
                    Active: {data.llm_backend.display_name} · {data.llm_backend.detail}
                  </span>
                )}
              </div>
              <div className="px-4 py-4 space-y-3">
                {!llm ? (
                  <div className="text-[13px] text-gray-400 dark:text-[#64748B]">Loading…</div>
                ) : (
                  <>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[11px] font-medium text-gray-600 dark:text-[#94A3B8] mb-1">Provider</label>
                        <select
                          className={inputCls}
                          value={llmSource}
                          onChange={e => onSelectProvider(e.target.value)}
                        >
                          {!llmSource && <option value="">— pick a provider —</option>}
                          {llm.providers.map(p => (
                            <option key={p.name} value={p.name} disabled={!p.configured}>
                              {p.label}{p.configured ? '' : ' — not configured'}
                            </option>
                          ))}
                        </select>
                        {selectedProvider && !selectedProvider.configured && selectedProvider.note && (
                          <div className="text-[11px] text-amber-600 dark:text-amber-400 mt-1">{selectedProvider.note}</div>
                        )}
                      </div>
                      <div>
                        <label className="block text-[11px] font-medium text-gray-600 dark:text-[#94A3B8] mb-1">Model</label>
                        {llmCustomMode ? (
                          <>
                            <input
                              type="text"
                              className={inputCls}
                              value={llmModel}
                              placeholder={customModelHint}
                              onChange={e => setLlmModel(e.target.value.trim())}
                              autoFocus
                            />
                            <button
                              type="button"
                              onClick={() => onSelectProvider(llmSource)}
                              className="text-[10px] text-indigo-500 dark:text-[#00A3FF] hover:underline mt-1"
                            >
                              ← back to curated list
                            </button>
                          </>
                        ) : (
                          <select
                            className={inputCls}
                            value={llmModel || ''}
                            onChange={e => onSelectModel(e.target.value)}
                            disabled={!llmSource}
                          >
                            {!llmSource && <option value="">— pick a provider first —</option>}
                            {availableModelsForSource.map(m => (
                              <option key={m} value={m}>{m}</option>
                            ))}
                            {llmSource && <option value={_CUSTOM}>Custom — type a model name…</option>}
                          </select>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center justify-between gap-3 pt-1">
                      <div className="text-[11px] text-gray-400 dark:text-[#64748B]">
                        Changes apply to <span className="font-medium">new chats</span>. Existing sessions keep their original model. To enable more providers, add the key to <span className="font-mono">.env</span> and restart.
                      </div>
                      <button
                        onClick={saveLlmPick}
                        disabled={llmSaving || !llmSource}
                        className="text-[12px] font-medium px-3 py-1.5 rounded-md bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 dark:disabled:bg-[#1E222B] text-white transition-colors"
                      >
                        {llmSaving ? 'Saving…' : 'Save'}
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Existing read-only agent settings */}
            <div className="bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#1E222B] bg-gray-50 dark:bg-[#15181F]">
                <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Agent Configuration</span>
              </div>
              {data ? data.agent.map((f, i) => (
                <div key={f.key} className={`flex items-center gap-4 px-4 py-[11px] ${i < data.agent.length - 1 ? 'border-b border-gray-200 dark:border-[#1E222B]' : ''}`}>
                  <div className="flex-[0_0_220px]">
                    <div className="text-[12px] font-medium text-gray-700 dark:text-[#CBD5E1]">{f.label}</div>
                    <div className="text-[11px] text-gray-400 dark:text-[#64748B] mt-0.5">{f.hint}</div>
                  </div>
                  <span className="font-mono text-[13px] font-medium text-gray-900 dark:text-[#E4E1EA]">{f.value}</span>
                </div>
              )) : (
                <div className="px-4 py-6 text-[13px] text-gray-400 dark:text-[#64748B] text-center">Loading…</div>
              )}
            </div>
          </div>
        )}

        {/* Integrations tab */}
        {tab === 'integrations' && (
          <div className="space-y-4">

            {/* Slack — live integration */}
            <div className="bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#1E222B] bg-gray-50 dark:bg-[#15181F] flex items-center justify-between">
                <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Slack</span>
                <span className={cn(
                  'text-[10px] font-semibold px-1.5 py-0.5 rounded',
                  slackConfigured
                    ? 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10'
                    : 'text-gray-500 dark:text-[#64748B] bg-gray-100 dark:bg-[#1E222B]'
                )}>
                  {slackConfigured ? 'Configured' : 'Not configured'}
                </span>
              </div>

              <div className="px-[18px] py-[14px] flex items-start gap-3">
                <div className="w-[34px] h-[34px] bg-gray-100 dark:bg-[#1E222B] rounded-lg flex items-center justify-center shrink-0 mt-0.5">
                  <SlackIcon size={20} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-medium text-gray-900 dark:text-[#E4E1EA] mb-0.5">Slack Notifications</div>
                  <div className="text-[13px] text-gray-500 dark:text-[#94A3B8] mb-3">
                    Sends a rich Block Kit message to your Slack channel after each investigation completes.
                  </div>
                  {!slackConfigured && (
                    <div className="text-[12px] text-gray-500 dark:text-[#94A3B8] bg-gray-50 dark:bg-[#15181F] border border-gray-200 dark:border-[#1E222B] rounded-md px-3 py-2 font-mono">
                      Add <span className="text-indigo-500 dark:text-[#00A3FF] font-semibold">SLACK_WEBHOOK_URL</span>=https://hooks.slack.com/… to your <span className="text-gray-700 dark:text-[#CBD5E1]">.env</span> file and restart
                    </div>
                  )}
                  {slackConfigured && (
                    <button
                      onClick={testSlack}
                      disabled={slackTesting}
                      className="flex items-center gap-1.5 text-[12px] font-medium px-3 py-[5px] bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 text-white rounded-[5px] transition-colors"
                    >
                      {slackTesting
                        ? <><Loader2 size={11} className="animate-spin" /> Sending…</>
                        : <><Send size={11} /> Send test message</>
                      }
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Telegram — live integration */}
            <div className="bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#1E222B] bg-gray-50 dark:bg-[#15181F] flex items-center justify-between">
                <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Telegram</span>
                <span className={cn(
                  'text-[10px] font-semibold px-1.5 py-0.5 rounded',
                  telegramConfigured
                    ? 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10'
                    : 'text-gray-500 dark:text-[#64748B] bg-gray-100 dark:bg-[#1E222B]'
                )}>
                  {telegramConfigured ? 'Configured' : 'Not configured'}
                </span>
              </div>
              <div className="px-[18px] py-[14px] flex items-start gap-3">
                <div className="w-[34px] h-[34px] bg-gray-100 dark:bg-[#1E222B] rounded-lg flex items-center justify-center shrink-0 mt-0.5">
                  <TelegramIcon size={20} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-medium text-gray-900 dark:text-[#E4E1EA] mb-0.5">Telegram Notifications</div>
                  <div className="text-[13px] text-gray-500 dark:text-[#94A3B8] mb-3">
                    Sends a formatted message to your Telegram bot after each investigation completes.
                  </div>
                  {!telegramConfigured && (
                    <div className="text-[12px] text-gray-500 dark:text-[#94A3B8] bg-gray-50 dark:bg-[#15181F] border border-gray-200 dark:border-[#1E222B] rounded-md px-3 py-2 font-mono space-y-1">
                      <div>Add <span className="text-indigo-500 dark:text-[#00A3FF] font-semibold">TELEGRAM_BOT_TOKEN</span>=123456:ABC-… to your <span className="text-gray-700 dark:text-[#CBD5E1]">.env</span> file</div>
                      <div>Add <span className="text-indigo-500 dark:text-[#00A3FF] font-semibold">TELEGRAM_CHAT_ID</span>=-100… to your <span className="text-gray-700 dark:text-[#CBD5E1]">.env</span> file and restart</div>
                    </div>
                  )}
                  {telegramConfigured && (
                    <button
                      onClick={testTelegram}
                      disabled={telegramTesting}
                      className="flex items-center gap-1.5 text-[12px] font-medium px-3 py-[5px] bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 text-white rounded-[5px] transition-colors"
                    >
                      {telegramTesting
                        ? <><Loader2 size={11} className="animate-spin" /> Sending…</>
                        : <><Send size={11} /> Send test message</>
                      }
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Coming soon integrations */}
            <div className="bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              {COMING_SOON_INTEGRATIONS.map((intg, i) => (
                <div key={i} className={`flex items-center gap-3 px-[18px] py-[14px] ${i < COMING_SOON_INTEGRATIONS.length - 1 ? 'border-b border-gray-200 dark:border-[#1E222B]' : ''}`}>
                  <div className="w-[34px] h-[34px] bg-gray-100 dark:bg-[#1E222B] rounded-lg flex items-center justify-center shrink-0">
                    <IntegrationIcon name={intg.iconKey} size={20} />
                  </div>
                  <div className="flex-1">
                    <div className="text-[14px] font-medium text-gray-900 dark:text-[#E4E1EA]">{intg.name}</div>
                    <div className="text-[13px] text-gray-500 dark:text-[#94A3B8]">{intg.desc}</div>
                  </div>
                  <span className="text-[11px] font-medium text-gray-400 dark:text-[#64748B] bg-gray-100 dark:bg-[#1E222B] px-2 py-[3px] rounded-full">
                    Coming soon
                  </span>
                </div>
              ))}
            </div>

            <a href="https://openrouter.ai/models" target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-[13px] text-indigo-500 dark:text-[#00A3FF] hover:text-indigo-600 dark:hover:text-[#0086D6] transition-colors">
              Browse available models on OpenRouter <ExternalLink size={13} />
            </a>
          </div>
        )}

        {/* AWS Configuration tab */}
        {tab === 'aws' && (
          <div className="space-y-5">

            {/* Config card */}
            <div className="bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#1E222B] bg-gray-50 dark:bg-[#15181F] flex items-center justify-between">
                <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Event Detection</span>
                <button
                  onClick={saveAwsConfig}
                  disabled={awsSaving}
                  className="flex items-center gap-1.5 text-[12px] font-medium px-3 py-1 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 text-white rounded-md transition-colors"
                >
                  {awsSaving ? <Loader2 size={11} className="animate-spin" /> : 'Save'}
                </button>
              </div>

              <div className="divide-y divide-gray-100 dark:divide-[#1E222B]">
                {[
                  { label: 'SQS Queue URL', hint: 'Event consumer polls this queue for CloudWatch alarms', value: sqsUrl, set: setSqsUrl, placeholder: 'https://sqs.us-east-1.amazonaws.com/123456789012/opendevops' },
                  { label: 'AWS Region',    hint: 'Region for SQS and EventBridge resources', value: awsRegion, set: setAwsRegion, placeholder: 'us-east-1' },
                ].map(({ label, hint, value, set, placeholder }) => (
                  <div key={label} className="flex items-start gap-4 px-4 py-[11px]">
                    <div className="flex-[0_0_200px] pt-0.5">
                      <div className="text-[12px] font-medium text-gray-700 dark:text-[#CBD5E1]">{label}</div>
                      <div className="text-[11px] text-gray-400 dark:text-[#64748B] mt-0.5 leading-relaxed">{hint}</div>
                    </div>
                    <input
                      value={value}
                      onChange={e => set(e.target.value)}
                      placeholder={placeholder}
                      className={inputCls}
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Event Monitoring card */}
            <div className="bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#1E222B] bg-gray-50 dark:bg-[#15181F] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Event Monitoring</span>
                  <span className={cn(
                    'flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded',
                    infraEnabled
                      ? 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10'
                      : 'text-gray-500 dark:text-[#64748B] bg-gray-100 dark:bg-[#1E222B]'
                  )}>
                    <Radio size={9} />
                    {infraEnabled ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
                {infraEnabled ? (
                  <button
                    onClick={teardownInfra}
                    disabled={infraBusy}
                    className="flex items-center gap-1.5 text-[12px] font-medium px-3 py-1 text-red-500 border border-red-200 dark:border-red-500/30 rounded-md hover:bg-red-50 dark:hover:bg-red-500/10 disabled:opacity-50 transition-colors"
                  >
                    {infraBusy ? <Loader2 size={11} className="animate-spin" /> : <><Trash2 size={11} /> Teardown</>}
                  </button>
                ) : (
                  <button
                    onClick={createInfra}
                    disabled={infraBusy}
                    className="flex items-center gap-1.5 text-[12px] font-medium px-3 py-1 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 text-white rounded-md transition-colors"
                  >
                    {infraBusy ? <Loader2 size={11} className="animate-spin" /> : <><Zap size={11} /> Create Infrastructure</>}
                  </button>
                )}
              </div>
              <div className="px-4 py-[11px]">
                {infraEnabled ? (
                  <div className="space-y-1 text-[13px]">
                    <div className="flex items-center gap-2">
                      <span className="text-gray-400 dark:text-[#64748B] flex-[0_0_100px]">Queue URL</span>
                      <span className="font-mono text-[12px] text-gray-700 dark:text-[#CBD5E1] truncate">{sqsUrl || '—'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-gray-400 dark:text-[#64748B] flex-[0_0_100px]">Rules</span>
                      <span className="text-gray-700 dark:text-[#CBD5E1]">{Object.keys(infraRules).length || 9} EventBridge rules active</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-[13px] text-gray-400 dark:text-[#64748B]">
                    Creates an SQS queue and 9 EventBridge rules to automatically detect and investigate AWS incidents.
                  </p>
                )}
              </div>
            </div>

            {/* Permissions card */}
            <div className="bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#1E222B] bg-gray-50 dark:bg-[#15181F] flex items-center justify-between">
                <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">AWS Permissions</span>
                <button
                  onClick={checkPerms}
                  disabled={awsChecking}
                  className="flex items-center gap-1.5 text-[12px] font-medium px-3 py-1 text-gray-600 dark:text-[#94A3B8] border border-gray-200 dark:border-[#1E222B] rounded-md hover:bg-gray-50 dark:hover:bg-[#1E222B] disabled:opacity-50 transition-colors"
                >
                  {awsChecking
                    ? <><Loader2 size={11} className="animate-spin" /> Checking…</>
                    : <><Shield size={11} /> {total > 0 ? 'Re-check' : 'Run checks'}</>
                  }
                </button>
              </div>

              {total === 0 && !awsChecking && (
                <div className="px-4 py-5 text-[13px] text-gray-400 dark:text-[#64748B] text-center">
                  Click <span className="font-medium">"Run checks"</span> to verify IAM permissions for each AWS service.
                </div>
              )}

              {total > 0 && (
                <>
                  <div className="px-4 py-[9px] border-b border-gray-100 dark:border-[#1E222B] flex items-center gap-3">
                    <div className="flex-1 h-1.5 bg-gray-100 dark:bg-[#1E222B] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-500 rounded-full transition-all duration-700"
                        style={{ width: `${(passed / total) * 100}%` }}
                      />
                    </div>
                    <span className="text-[11px] font-semibold text-gray-500 dark:text-[#64748B] tabular-nums">{passed}/{total} passed</span>
                  </div>

                  {Object.entries(perms).map(([svc, r], i) => (
                    <div key={svc} className={cn(
                      'flex items-center gap-3 px-4 py-[9px]',
                      i < total - 1 ? 'border-b border-gray-100 dark:border-[#1E222B]' : ''
                    )}>
                      <div className="shrink-0">
                        {r.passed
                          ? <CheckCircle size={14} className="text-emerald-500" />
                          : r.passed === null
                            ? <AlertTriangle size={14} className="text-amber-500" />
                            : <XCircle size={14} className="text-red-500" />
                        }
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="text-[12px] font-medium text-gray-700 dark:text-[#CBD5E1]">{SVC[svc]?.label || svc}</span>
                        <span className="text-[12px] text-gray-400 dark:text-[#64748B] ml-2">{SVC[svc]?.desc}</span>
                        {!r.passed && r.error && (
                          <p className="text-[11px] text-red-500 dark:text-red-400 truncate mt-0.5">{r.error}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>

          </div>
        )}

        {/* Preferences tab */}
        {tab === 'preferences' && (
          <div className="bg-white dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
            <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#1E222B] bg-gray-50 dark:bg-[#15181F]">
              <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Appearance</span>
            </div>
            <div className="flex items-center justify-between px-4 py-[14px]">
              <div>
                <div className="text-[14px] font-medium text-gray-700 dark:text-[#CBD5E1]">Dark mode</div>
                <div className="text-[13px] text-gray-400 dark:text-[#64748B] mt-0.5">Switch between light and dark theme</div>
              </div>
              <button
                onClick={toggle}
                title="Toggle dark mode"
                className="relative w-9 h-5 rounded-full shrink-0 transition-colors duration-200"
                style={{ background: theme === 'dark' ? '#00A3FF' : '#E5E7EB' }}
              >
                <span
                  className="absolute top-[2px] w-4 h-4 rounded-full bg-white flex items-center justify-center text-[9px] transition-all duration-200"
                  style={{ left: theme === 'dark' ? '18px' : '2px' }}
                >
                  {theme === 'dark' ? '🌙' : '☀️'}
                </span>
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
