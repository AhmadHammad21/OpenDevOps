import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Loader2, Terminal, Eye, EyeOff, CheckCircle, XCircle, AlertTriangle, ChevronRight, Check } from 'lucide-react';
import { cn } from '../lib/utils';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../lib/api';

const inp = 'w-full text-base text-gray-900 dark:text-white bg-gray-50 dark:bg-[#18181B] border border-gray-200 dark:border-[#27272A] rounded-xl px-4 py-3.5 outline-none focus:border-indigo-500 dark:focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/10 transition-all placeholder:text-gray-400 dark:placeholder:text-[#52525B]';

const AWS_REGIONS = [
  'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
  'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1',
  'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1', 'ap-south-1',
  'ca-central-1', 'sa-east-1',
];

const SVC: Record<string, { label: string; desc: string; required?: boolean }> = {
  cloudwatch: { label: 'CloudWatch',  desc: 'Alarms, metrics, logs',  required: true },
  lambda:     { label: 'Lambda',      desc: 'Serverless functions',   required: true },
  sqs:        { label: 'SQS',         desc: 'Event queue',            required: true },
  events:     { label: 'EventBridge', desc: 'Event rules',            required: true },
  ecs:        { label: 'ECS',         desc: 'Container services' },
  rds:        { label: 'RDS',         desc: 'Database events' },
  ec2:        { label: 'EC2',         desc: 'Instance status' },
  iam:        { label: 'IAM / STS',   desc: 'Identity & access' },
  sns:        { label: 'SNS',         desc: 'Alert publishing' },
  cloudtrail: { label: 'CloudTrail',  desc: 'API event history' },
};

const RULES = [
  { name: 'CloudWatch Alarm State Change',               src: 'aws.cloudwatch' },
  { name: 'Lambda Invocation Failure',                   src: 'aws.lambda' },
  { name: 'Lambda Throttling',                           src: 'aws.lambda' },
  { name: 'ECS Task Stopped (non-zero exit)',            src: 'aws.ecs' },
  { name: 'EC2 Instance Terminated',                     src: 'aws.ec2' },
  { name: 'RDS DB Events (failure / failover)',          src: 'aws.rds' },
  { name: 'AWS Health Event',                            src: 'aws.health' },
  { name: 'CodeDeploy Deployment Failure',               src: 'aws.codedeploy' },
  { name: 'GuardDuty Finding',                           src: 'aws.guardduty' },
];

interface PermResult { passed: boolean | null; error: string | null }

type Step = 1 | 2 | 3 | 4;

export default function InitPage() {
  const navigate = useNavigate();
  const { user, login, authRequired, loading: authLoading } = useAuth();

  const [step, setStep] = useState<Step>(1);

  // Step 1
  const [orgName,  setOrgName]  = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPw,   setShowPw]   = useState(false);

  // Step 2
  const [region,   setRegion]   = useState('us-east-1');
  const [snsArn,   setSnsArn]   = useState('');

  // Step 3
  const [perms,    setPerms]    = useState<Record<string, PermResult>>({});

  // Step 4
  const [infraDone, setInfraDone] = useState(false);
  const [queueUrl,  setQueueUrl]  = useState('');
  const [showSkipDisclaimer, setShowSkipDisclaimer] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');

  useEffect(() => {
    if (authLoading) return;
    if (user && user.role !== 'admin') { navigate('/', { replace: true }); return; }
    apiFetch('/api/init/status')
      .then(r => r.json())
      .then(d => {
        setRegion(d.aws_region || 'us-east-1');
        setSnsArn(d.sns_topic_arn || '');
        if (d.initialized && (d.has_user || !d.auth_enabled)) {
          navigate('/', { replace: true });
          return;
        }
        setStep((user || !authRequired) ? 2 : 1);
      })
      .catch(() => {});
  }, [authLoading, authRequired, navigate, user]);

  // ─── Step 1: create admin account ─────────────────────────────────────────
  const createUser = async () => {
    if (!username.trim() || !password.trim()) { setError('Email and password are required'); return; }
    setLoading(true); setError('');
    try {
      const r = await apiFetch('/api/init/create-user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const data = await r.json();
      if (!r.ok || data.error) { setError(data.detail || data.error || 'Failed to create account'); return; }
      if (authRequired) await login(username.trim(), password);
      setStep(2);
    } finally {
      setLoading(false);
    }
  };

  // ─── Step 2: save AWS config ───────────────────────────────────────────────
  const saveConfig = async () => {
    setLoading(true); setError('');
    try {
      const r = await apiFetch('/api/init/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ aws_region: region, sns_topic_arn: snsArn, sqs_queue_url: '', org_name: orgName.trim() }),
      });
      if (!r.ok) { setError('Failed to save configuration'); return; }
      setStep(3);
    } finally {
      setLoading(false);
    }
  };

  // ─── Step 3: check permissions ─────────────────────────────────────────────
  const checkPerms = async () => {
    setLoading(true); setError('');
    try {
      const r = await apiFetch('/api/init/check-permissions', { method: 'POST' });
      const d = await r.json() as { permissions: Record<string, PermResult> };
      setPerms(d.permissions);
    } catch {
      setError('Permission check failed');
    } finally {
      setLoading(false);
    }
  };

  // ─── Step 4: create infrastructure ────────────────────────────────────────
  const createInfra = async () => {
    setLoading(true); setError('');
    try {
      const r = await apiFetch('/api/init/complete', { method: 'POST' });
      const d = await r.json() as { initialized: boolean; error?: string | null; detail?: string };
      if (!r.ok || !d.initialized) { setError(d.error || d.detail || 'Infrastructure setup failed'); return; }
      setInfraDone(true);
      // Fetch the queue URL from init status to display in summary
      const s = await apiFetch('/api/init/status').then(res => res.json());
      setQueueUrl(s.sqs_queue_url || 'opendevops-agent-events');
    } finally {
      setLoading(false);
    }
  };

  const finishWithoutInfra = async () => {
    setLoading(true); setError('');
    try {
      const r = await apiFetch('/api/init/skip-services', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ services: ['event-monitoring'] }),
      });
      if (!r.ok) throw new Error('finish failed');
      navigate('/', { replace: true });
    } catch {
      setError('Failed to finish setup');
    } finally {
      setLoading(false);
    }
  };

  const requiredPassed = Object.entries(perms)
    .filter(([svc]) => SVC[svc]?.required)
    .every(([, r]) => r.passed);
  const hasPerms = Object.keys(perms).length > 0;

  return (
    <div className="h-screen bg-white dark:bg-[#09090B] flex flex-col overflow-hidden">
      <header className="shrink-0 px-8 py-5 flex items-center gap-3">
        <div className="w-9 h-9 bg-gradient-to-br from-indigo-500 to-violet-600 rounded-xl flex items-center justify-center">
          <Terminal size={16} className="text-white" />
        </div>
        <span className="text-base font-semibold text-gray-900 dark:text-white">OpenDevOps</span>
      </header>

      <main className="flex-1 overflow-y-auto px-6 pb-16">
        <div className="w-full max-w-xl mx-auto pt-10">

          {/* Step indicator */}
          <div className="flex items-center gap-2 mb-10">
            {([1, 2, 3, 4] as Step[]).map((s, i) => (
              <div key={s} className="flex items-center gap-2">
                <div className={cn(
                  'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors',
                  step > s
                    ? 'bg-indigo-500 text-white'
                    : step === s
                      ? 'bg-indigo-500 text-white ring-4 ring-indigo-500/20'
                      : 'bg-gray-100 dark:bg-[#27272A] text-gray-400 dark:text-[#52525B]'
                )}>
                  {step > s ? <Check size={13} /> : s}
                </div>
                {i < 3 && (
                  <div className={cn(
                    'h-px w-8 transition-colors',
                    step > s ? 'bg-indigo-500' : 'bg-gray-200 dark:bg-[#27272A]'
                  )} />
                )}
              </div>
            ))}
            <span className="ml-2 text-xs text-gray-400 dark:text-[#52525B]">Step {step} of 4</span>
          </div>

          {/* ─── Step 1: Create Account ─────────────────────────────────── */}
          {step === 1 && (
            <>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight mb-3">Create your account</h1>
              <p className="text-lg text-gray-500 dark:text-[#A1A1AA] mb-10 leading-relaxed">
                Set up the admin credentials you'll use to access the dashboard.
              </p>
              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-[#D4D4D8] mb-2">Email</label>
                  <input type="email" value={username} onChange={e => setUsername(e.target.value)} placeholder="you@example.com" className={inp} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-[#D4D4D8] mb-2">Password</label>
                  <div className="relative">
                    <input
                      type={showPw ? 'text' : 'password'}
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && createUser()}
                      placeholder="At least 8 characters"
                      className={inp + ' pr-11'}
                    />
                    <button type="button" onClick={() => setShowPw(p => !p)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-white transition-colors">
                      {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>
              </div>
              {error && <p className="mt-4 text-sm text-red-500">{error}</p>}
              <button onClick={createUser} disabled={loading}
                className="w-full mt-10 flex items-center justify-center gap-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 text-base font-semibold py-4 rounded-xl hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50">
                {loading ? <Loader2 size={18} className="animate-spin" /> : <>Create account <ArrowRight size={16} /></>}
              </button>
            </>
          )}

          {/* ─── Step 2: AWS Configuration ──────────────────────────────── */}
          {step === 2 && (
            <>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight mb-3">AWS Configuration</h1>
              <p className="text-lg text-gray-500 dark:text-[#A1A1AA] mb-10 leading-relaxed">
                Configure the AWS region and optional SNS topic for alert delivery.
              </p>
              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-[#D4D4D8] mb-2">
                    Organization name <span className="text-gray-400 dark:text-[#52525B] font-normal">(optional)</span>
                  </label>
                  <input value={orgName} onChange={e => setOrgName(e.target.value)} placeholder="Acme Corp" className={inp} />
                  <p className="mt-1.5 text-xs text-gray-400 dark:text-[#52525B]">
                    Used to group users. You can add team members later from Settings.
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-[#D4D4D8] mb-2">AWS Region</label>
                  <select
                    value={region}
                    onChange={e => setRegion(e.target.value)}
                    className={inp + ' cursor-pointer'}
                  >
                    {AWS_REGIONS.map(r => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-[#D4D4D8] mb-2">
                    SNS Topic ARN <span className="text-gray-400 dark:text-[#52525B] font-normal">(optional)</span>
                  </label>
                  <input
                    value={snsArn}
                    onChange={e => setSnsArn(e.target.value)}
                    placeholder="arn:aws:sns:us-east-1:123456789012:alerts"
                    className={inp}
                  />
                  <p className="mt-1.5 text-xs text-gray-400 dark:text-[#52525B]">
                    Leave empty to skip SNS notifications — alerts will still appear in the monitoring page.
                  </p>
                </div>
              </div>
              {error && <p className="mt-4 text-sm text-red-500">{error}</p>}
              <button onClick={saveConfig} disabled={loading}
                className="w-full mt-10 flex items-center justify-center gap-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 text-base font-semibold py-4 rounded-xl hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50">
                {loading ? <Loader2 size={18} className="animate-spin" /> : <>Continue <ArrowRight size={16} /></>}
              </button>
              <button onClick={finishWithoutInfra} disabled={loading}
                className="w-full mt-3 text-sm text-gray-400 dark:text-[#52525B] hover:text-gray-600 dark:hover:text-[#A1A1AA] transition-colors py-2">
                Skip setup — configure later in Settings
              </button>
            </>
          )}

          {/* ─── Step 3: Permission Check ────────────────────────────────── */}
          {step === 3 && (
            <>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight mb-3">Check permissions</h1>
              <p className="text-lg text-gray-500 dark:text-[#A1A1AA] mb-2 leading-relaxed">
                Verify that the IAM user or role has the required permissions for each AWS service.
              </p>
              <p className="text-sm text-gray-400 dark:text-[#71717A] mb-8">
                Need to set up IAM permissions first? See{' '}
                <a href="https://github.com/AhmadHammad21/OpenDevOps/blob/main/docs/iam_setup.md"
                   target="_blank" rel="noopener noreferrer"
                   className="text-indigo-500 dark:text-[#818CF8] hover:underline">
                  docs/iam_setup.md
                </a>
                {' '}for the exact policy JSON.
              </p>

              {!hasPerms ? (
                <button onClick={checkPerms} disabled={loading}
                  className="w-full flex items-center justify-center gap-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 text-base font-semibold py-4 rounded-xl hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50">
                  {loading ? <Loader2 size={18} className="animate-spin" /> : 'Check permissions'}
                </button>
              ) : (
                <>
                  <div className="rounded-xl border border-gray-200 dark:border-[#27272A] overflow-hidden mb-6">
                    {Object.entries(SVC).map(([svc, info], i) => {
                      const r = perms[svc];
                      return (
                        <div key={svc} className={cn(
                          'flex items-center gap-3 px-4 py-3',
                          i < Object.keys(SVC).length - 1 ? 'border-b border-gray-100 dark:border-[#27272A]' : ''
                        )}>
                          <div className="shrink-0">
                            {!r
                              ? <div className="w-[14px] h-[14px] rounded-full bg-gray-200 dark:bg-[#27272A]" />
                              : r.passed
                                ? <CheckCircle size={14} className="text-emerald-500" />
                                : r.passed === null
                                  ? <AlertTriangle size={14} className="text-amber-500" />
                                  : <XCircle size={14} className="text-red-500" />
                            }
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-gray-900 dark:text-white">{info.label}</span>
                              <span className="text-xs text-gray-400 dark:text-[#52525B]">{info.desc}</span>
                              {info.required && (
                                <span className="text-[10px] font-semibold text-indigo-500 dark:text-[#818CF8] bg-indigo-50 dark:bg-indigo-500/10 px-1.5 py-0.5 rounded">Required</span>
                              )}
                            </div>
                            {r && !r.passed && r.error && (
                              <p className="text-xs text-red-500 dark:text-red-400 mt-0.5 truncate">{r.error}</p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {!requiredPassed && (
                    <div className="mb-4 p-3.5 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 text-sm text-amber-700 dark:text-amber-300">
                      Some required permissions are missing. Event monitoring may not work correctly.
                      You can still continue — fix the IAM permissions and re-check in Settings.
                    </div>
                  )}

                  {error && <p className="mb-4 text-sm text-red-500">{error}</p>}

                  <button onClick={() => setStep(4)}
                    className="w-full flex items-center justify-center gap-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 text-base font-semibold py-4 rounded-xl hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors">
                    Continue anyway <ChevronRight size={16} />
                  </button>

                  <button onClick={checkPerms} disabled={loading}
                    className="w-full mt-3 flex items-center justify-center gap-2 text-sm font-medium text-gray-500 dark:text-[#A1A1AA] hover:text-gray-700 dark:hover:text-white py-2 transition-colors">
                    {loading ? <Loader2 size={14} className="animate-spin" /> : 'Re-check'}
                  </button>
                </>
              )}
            </>
          )}

          {/* ─── Step 4: Enable Event Monitoring ────────────────────────── */}
          {step === 4 && (
            <>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight mb-3">Enable event monitoring</h1>
              <p className="text-lg text-gray-500 dark:text-[#A1A1AA] mb-8 leading-relaxed">
                Create the SQS queue and 9 EventBridge rules that feed incidents into the investigation pipeline.
              </p>

              {!infraDone ? (
                <>
                  {/* Rule list preview */}
                  <div className="rounded-xl border border-gray-200 dark:border-[#27272A] overflow-hidden mb-6">
                    {RULES.map((rule, i) => (
                      <div key={rule.name} className={cn(
                        'flex items-center gap-3 px-4 py-3',
                        i < RULES.length - 1 ? 'border-b border-gray-100 dark:border-[#27272A]' : ''
                      )}>
                        <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 dark:bg-[#818CF8] shrink-0" />
                        <div>
                          <span className="text-sm text-gray-900 dark:text-white">{rule.name}</span>
                          <span className="text-xs text-gray-400 dark:text-[#52525B] ml-2">{rule.src}</span>
                        </div>
                      </div>
                    ))}
                  </div>

                  {error && <p className="mb-4 text-sm text-red-500">{error}</p>}

                  <button onClick={createInfra} disabled={loading}
                    className="w-full flex items-center justify-center gap-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 text-base font-semibold py-4 rounded-xl hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50">
                    {loading
                      ? <><Loader2 size={18} className="animate-spin" /> Creating infrastructure…</>
                      : 'Create infrastructure'
                    }
                  </button>

                  {/* Skip option */}
                  <button onClick={() => setShowSkipDisclaimer(p => !p)}
                    className="w-full mt-3 text-sm text-gray-400 dark:text-[#52525B] hover:text-gray-600 dark:hover:text-[#A1A1AA] transition-colors py-2">
                    Skip for now — I'll enable this in Settings later
                  </button>

                  {showSkipDisclaimer && (
                    <div className="mt-3 p-4 rounded-xl bg-gray-50 dark:bg-[#18181B] border border-gray-200 dark:border-[#27272A]">
                      <p className="text-sm font-semibold text-gray-700 dark:text-[#D4D4D8] mb-2">Without event monitoring:</p>
                      <ul className="space-y-1 mb-3">
                        {[
                          'Automatic incident detection',
                          'Event-triggered investigations',
                          'Slack / SNS alert delivery',
                          'Monitoring page will be empty',
                        ].map(item => (
                          <li key={item} className="flex items-center gap-2 text-sm text-red-500 dark:text-red-400">
                            <XCircle size={13} /> {item}
                          </li>
                        ))}
                      </ul>
                      <p className="text-xs text-gray-400 dark:text-[#52525B]">
                        You can enable this anytime from <span className="font-medium text-gray-600 dark:text-[#A1A1AA]">Settings → AWS Configuration</span>.
                      </p>
                      <button onClick={finishWithoutInfra} disabled={loading}
                        className="mt-3 w-full text-sm font-medium text-gray-700 dark:text-[#D4D4D8] bg-white dark:bg-[#27272A] border border-gray-200 dark:border-[#3F3F46] rounded-lg py-2.5 hover:bg-gray-50 dark:hover:bg-[#3F3F46] transition-colors">
                        Go to dashboard anyway
                      </button>
                    </div>
                  )}
                </>
              ) : (
                // Success summary
                <>
                  <div className="rounded-xl border border-emerald-200 dark:border-emerald-500/20 bg-emerald-50 dark:bg-emerald-500/5 p-5 mb-6">
                    <div className="flex items-center gap-2 mb-3">
                      <CheckCircle size={18} className="text-emerald-500 shrink-0" />
                      <span className="text-sm font-semibold text-emerald-700 dark:text-emerald-300">Infrastructure created successfully</span>
                    </div>
                    <div className="space-y-1.5 text-sm text-emerald-700 dark:text-emerald-300">
                      <p>✓ SQS queue: <span className="font-mono text-xs">{queueUrl || 'opendevops-agent-events'}</span></p>
                      <p>✓ {RULES.length} EventBridge rules active</p>
                    </div>
                  </div>

                  <div className="rounded-xl border border-gray-200 dark:border-[#27272A] overflow-hidden mb-8">
                    {RULES.map((rule, i) => (
                      <div key={rule.name} className={cn(
                        'flex items-center gap-3 px-4 py-3',
                        i < RULES.length - 1 ? 'border-b border-gray-100 dark:border-[#27272A]' : ''
                      )}>
                        <CheckCircle size={13} className="text-emerald-500 shrink-0" />
                        <span className="text-sm text-gray-900 dark:text-white">{rule.name}</span>
                      </div>
                    ))}
                  </div>

                  <button onClick={() => navigate('/monitoring', { replace: true })}
                    className="w-full flex items-center justify-center gap-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 text-base font-semibold py-4 rounded-xl hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors">
                    Go to monitoring <ArrowRight size={16} />
                  </button>
                  <button onClick={() => navigate('/', { replace: true })}
                    className="w-full mt-3 text-sm text-gray-400 dark:text-[#52525B] hover:text-gray-600 dark:hover:text-[#A1A1AA] transition-colors py-2">
                    Go to dashboard
                  </button>
                </>
              )}
            </>
          )}

        </div>
      </main>
    </div>
  );
}
