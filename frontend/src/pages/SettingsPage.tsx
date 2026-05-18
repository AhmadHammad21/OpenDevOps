import { useState, useEffect } from 'react';
import { ExternalLink, Eye, EyeOff, Key, CheckCircle, XCircle, AlertTriangle, Loader2, Shield, Radio, Trash2, Zap, Send } from 'lucide-react';
import { SlackIcon, IntegrationIcon } from '../components/icons/IntegrationIcon';
import { toast } from 'sonner';
import { apiFetch } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { cn } from '../lib/utils';

interface EnvVar   { key: string; value: string; secret: boolean }
interface AgentVar { key: string; label: string; value: string; hint: string }
interface SettingsData { env: EnvVar[]; agent: AgentVar[] }
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
  { name: 'GitHub',    desc: 'Connect your repositories',   iconKey: 'github' },
  { name: 'PagerDuty', desc: 'Alert on failures',           iconKey: 'pagerduty' },
  { name: 'Datadog',   desc: 'Send metrics and traces',     iconKey: 'datadog' },
  { name: 'Telegram',  desc: 'Get alerts via Telegram bot', iconKey: 'telegram' },
];

const inputCls = 'w-full font-mono text-[12px] text-gray-700 dark:text-[#CBD5E1] bg-white dark:bg-[#0F0F12] border border-gray-200 dark:border-[#27272F] rounded-md px-3 py-1.5 outline-none focus:border-indigo-500 dark:focus:border-[#818CF8] focus:ring-1 focus:ring-indigo-500/20 dark:focus:ring-[#818CF8]/20 transition-all placeholder:text-gray-300 dark:placeholder:text-[#3F3F47]';

export default function SettingsPage() {
  const { isAdmin }   = useAuth();
  const { theme, toggle } = useTheme();
  const [tab, setTab] = useState<Tab>(isAdmin ? 'aws' : 'env');
  const [shown, setShown] = useState<Record<string, boolean>>({});
  const [data, setData]   = useState<SettingsData | null>(null);

  // Integrations tab state
  const [slackConfigured, setSlackConfigured] = useState(false);
  const [slackTesting,    setSlackTesting]    = useState(false);

  // AWS tab state
  const [snsArn,        setSnsArn]        = useState('');
  const [sqsUrl,        setSqsUrl]        = useState('');
  const [awsRegion,     setAwsRegion]     = useState('');
  const [awsSaving,     setAwsSaving]     = useState(false);
  const [awsChecking,   setAwsChecking]   = useState(false);
  const [perms,         setPerms]         = useState<Record<string, PermResult>>({});
  // Event monitoring section
  const [infraEnabled,  setInfraEnabled]  = useState(false);
  const [infraRules,    setInfraRules]    = useState<Record<string, string>>({});
  const [infraBusy,     setInfraBusy]     = useState(false);

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
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (tab !== 'aws') return;
    apiFetch('/api/init/status')
      .then(r => r.json())
      .then(d => {
        setSnsArn(d.sns_topic_arn || '');
        setSqsUrl(d.sqs_queue_url || '');
        setAwsRegion(d.aws_region || '');
        setInfraEnabled(!!d.event_infra_enabled);
        setInfraRules(d.eventbridge_rule_arns || {});
      })
      .catch(() => {});
  }, [tab]);

  const toggleShow = (k: string) => setShown(p => ({ ...p, [k]: !p[k] }));

  const saveAwsConfig = async () => {
    setAwsSaving(true);
    try {
      const r = await apiFetch('/api/init/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sns_topic_arn: snsArn, sqs_queue_url: sqsUrl, aws_region: awsRegion }),
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

  const passed = Object.values(perms).filter(r => r.passed).length;
  const total  = Object.keys(perms).length;

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50 dark:bg-[#0F0F12] min-h-0">
      <div className="bg-white dark:bg-[#18181C] border-b border-gray-200 dark:border-[#27272F] px-7 py-[14px]">
        <div className="text-[16px] font-bold text-gray-900 dark:text-[#F1F5F9] tracking-[-0.02em]">Settings</div>
        <div className="text-[13px] text-gray-500 dark:text-[#94A3B8] mt-0.5">
          View your agent configuration. Edit <code className="font-mono text-[12px] bg-gray-100 dark:bg-[#27272F] px-1 rounded">.env</code> and restart to apply environment changes.
        </div>
      </div>

      <div className="flex bg-white dark:bg-[#18181C] border-b border-gray-200 dark:border-[#27272F] px-7">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-3.5 py-2.5 text-[14px] font-medium transition-colors border-b-2 -mb-px ${
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

        {/* Environment tab */}
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
                  <span className="font-mono text-[13px] font-medium text-gray-700 dark:text-[#CBD5E1]">{v.key}</span>
                </div>
                <div className="flex-1 font-mono text-[13px] text-gray-500 dark:text-[#94A3B8] overflow-hidden text-ellipsis whitespace-nowrap">
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

        {/* Agent config tab */}
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

        {/* Integrations tab */}
        {tab === 'integrations' && (
          <div className="space-y-4">

            {/* Slack — live integration */}
            <div className="bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#27272F] bg-gray-50 dark:bg-[#1E1E24] flex items-center justify-between">
                <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Slack</span>
                <span className={cn(
                  'text-[10px] font-semibold px-1.5 py-0.5 rounded',
                  slackConfigured
                    ? 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10'
                    : 'text-gray-500 dark:text-[#64748B] bg-gray-100 dark:bg-[#27272F]'
                )}>
                  {slackConfigured ? 'Configured' : 'Not configured'}
                </span>
              </div>

              <div className="px-[18px] py-[14px] flex items-start gap-3">
                <div className="w-[34px] h-[34px] bg-gray-100 dark:bg-[#27272F] rounded-lg flex items-center justify-center shrink-0 mt-0.5">
                  <SlackIcon size={20} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-medium text-gray-900 dark:text-[#F1F5F9] mb-0.5">Slack Notifications</div>
                  <div className="text-[13px] text-gray-500 dark:text-[#94A3B8] mb-3">
                    Sends a rich Block Kit message to your Slack channel after each investigation completes.
                  </div>
                  {!slackConfigured && (
                    <div className="text-[12px] text-gray-500 dark:text-[#94A3B8] bg-gray-50 dark:bg-[#1E1E24] border border-gray-200 dark:border-[#27272F] rounded-md px-3 py-2 font-mono">
                      Add <span className="text-indigo-500 dark:text-[#818CF8] font-semibold">SLACK_WEBHOOK_URL</span>=https://hooks.slack.com/… to your <span className="text-gray-700 dark:text-[#CBD5E1]">.env</span> file and restart
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

            {/* Coming soon integrations */}
            <div className="bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              {COMING_SOON_INTEGRATIONS.map((intg, i) => (
                <div key={i} className={`flex items-center gap-3 px-[18px] py-[14px] ${i < COMING_SOON_INTEGRATIONS.length - 1 ? 'border-b border-gray-200 dark:border-[#27272F]' : ''}`}>
                  <div className="w-[34px] h-[34px] bg-gray-100 dark:bg-[#27272F] rounded-lg flex items-center justify-center shrink-0">
                    <IntegrationIcon name={intg.iconKey} size={20} />
                  </div>
                  <div className="flex-1">
                    <div className="text-[14px] font-medium text-gray-900 dark:text-[#F1F5F9]">{intg.name}</div>
                    <div className="text-[13px] text-gray-500 dark:text-[#94A3B8]">{intg.desc}</div>
                  </div>
                  <span className="text-[11px] font-medium text-gray-400 dark:text-[#64748B] bg-gray-100 dark:bg-[#27272F] px-2 py-[3px] rounded-full">
                    Coming soon
                  </span>
                </div>
              ))}
            </div>

            <a href="https://openrouter.ai/models" target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-[13px] text-indigo-500 dark:text-[#818CF8] hover:text-indigo-600 dark:hover:text-[#6366F1] transition-colors">
              Browse available models on OpenRouter <ExternalLink size={13} />
            </a>
          </div>
        )}

        {/* AWS Configuration tab */}
        {tab === 'aws' && (
          <div className="space-y-5">

            {/* Config card */}
            <div className="bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#27272F] bg-gray-50 dark:bg-[#1E1E24] flex items-center justify-between">
                <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Event Detection</span>
                <button
                  onClick={saveAwsConfig}
                  disabled={awsSaving}
                  className="flex items-center gap-1.5 text-[12px] font-medium px-3 py-1 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 text-white rounded-md transition-colors"
                >
                  {awsSaving ? <Loader2 size={11} className="animate-spin" /> : 'Save'}
                </button>
              </div>

              <div className="divide-y divide-gray-100 dark:divide-[#27272F]">
                {[
                  { label: 'SNS Topic ARN', hint: 'Alerts are published here after each investigation', value: snsArn, set: setSnsArn, placeholder: 'arn:aws:sns:us-east-1:123456789012:alerts' },
                  { label: 'SQS Queue URL', hint: 'Event consumer polls this queue for CloudWatch alarms', value: sqsUrl, set: setSqsUrl, placeholder: 'https://sqs.us-east-1.amazonaws.com/123456789012/opendevops' },
                  { label: 'AWS Region',    hint: 'Region for SNS, SQS, and EventBridge resources', value: awsRegion, set: setAwsRegion, placeholder: 'us-east-1' },
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
            <div className="bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#27272F] bg-gray-50 dark:bg-[#1E1E24] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Event Monitoring</span>
                  <span className={cn(
                    'flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded',
                    infraEnabled
                      ? 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10'
                      : 'text-gray-500 dark:text-[#64748B] bg-gray-100 dark:bg-[#27272F]'
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
            <div className="bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#27272F] bg-gray-50 dark:bg-[#1E1E24] flex items-center justify-between">
                <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">AWS Permissions</span>
                <button
                  onClick={checkPerms}
                  disabled={awsChecking}
                  className="flex items-center gap-1.5 text-[12px] font-medium px-3 py-1 text-gray-600 dark:text-[#94A3B8] border border-gray-200 dark:border-[#27272F] rounded-md hover:bg-gray-50 dark:hover:bg-[#27272F] disabled:opacity-50 transition-colors"
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
                  <div className="px-4 py-[9px] border-b border-gray-100 dark:border-[#27272F] flex items-center gap-3">
                    <div className="flex-1 h-1.5 bg-gray-100 dark:bg-[#27272F] rounded-full overflow-hidden">
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
                      i < total - 1 ? 'border-b border-gray-100 dark:border-[#27272F]' : ''
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
          <div className="bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
            <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#27272F] bg-gray-50 dark:bg-[#1E1E24]">
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
                style={{ background: theme === 'dark' ? '#818CF8' : '#E5E7EB' }}
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
