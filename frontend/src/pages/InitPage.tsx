import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell, Shield, CheckCircle, XCircle, SkipForward,
  Loader2, ArrowRight, ArrowLeft, AlertTriangle, Zap, Terminal,
  Eye, EyeOff, Copy, Check,
} from 'lucide-react';
import { cn } from '../lib/utils';

interface PermResult { passed: boolean | null; error: string | null }

const STEPS = ['Account', 'Notifications', 'Permissions', 'Ready'] as const;

const SVC: Record<string, { label: string; desc: string }> = {
  cloudwatch: { label: 'CloudWatch',   desc: 'Alarms, metrics, logs' },
  cloudtrail: { label: 'CloudTrail',   desc: 'API event history' },
  ecs:        { label: 'ECS',          desc: 'Container services' },
  lambda:     { label: 'Lambda',       desc: 'Serverless functions' },
  ec2:        { label: 'EC2',          desc: 'Instance status' },
  rds:        { label: 'RDS',          desc: 'Database events' },
  iam:        { label: 'IAM / STS',    desc: 'Identity & access' },
  sns:        { label: 'SNS',          desc: 'Alert publishing' },
  sqs:        { label: 'SQS',          desc: 'Event queue' },
  events:     { label: 'EventBridge',  desc: 'Event rules' },
};

function extractRegion(arn: string): string {
  const p = arn.split(':');
  return p.length >= 4 && p[3] ? p[3] : '';
}

const inp = 'w-full text-base text-gray-900 dark:text-white bg-gray-50 dark:bg-[#18181B] border border-gray-200 dark:border-[#27272A] rounded-xl px-4 py-3.5 outline-none focus:border-indigo-500 dark:focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/10 transition-all placeholder:text-gray-400 dark:placeholder:text-[#52525B]';

export default function InitPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [userError, setUserError] = useState('');
  const [snsArn, setSnsArn] = useState('');
  const [region, setRegion] = useState('');
  const [perms, setPerms] = useState<Record<string, PermResult>>({});
  const [skipped, setSkipped] = useState<Set<string>>(new Set());
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch('/api/init/status').then(r => r.json()).then(d => {
      if (d.initialized) navigate('/', { replace: true });
      if (d.has_user) setStep(1);
      if (d.sns_topic_arn) { setSnsArn(d.sns_topic_arn); setRegion(extractRegion(d.sns_topic_arn) || d.aws_region || ''); }
      else if (d.aws_region) setRegion(d.aws_region);
    }).catch(() => {});
  }, [navigate]);

  const createUser = async () => {
    if (!username.trim() || !password.trim()) { setUserError('Both fields are required'); return; }
    setLoading(true); setUserError('');
    const r = await fetch('/api/init/create-user', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.trim(), password }),
    });
    const data = await r.json();
    setLoading(false);
    if (data.error) { setUserError(data.error); return; }
    setStep(1);
  };

  const handleSns = (v: string) => { setSnsArn(v); const r = extractRegion(v); if (r) setRegion(r); };

  const saveAndNext = async () => {
    setLoading(true);
    await fetch('/api/init/setup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sns_topic_arn: snsArn, aws_region: region }),
    });
    setLoading(false);
    setStep(2);
  };

  const checkPerms = async () => {
    setChecking(true);
    const r = await fetch('/api/init/check-permissions', { method: 'POST' });
    setPerms((await r.json()).permissions);
    setChecking(false);
  };

  const toggle = (s: string) => setSkipped(p => { const n = new Set(p); n.has(s) ? n.delete(s) : n.add(s); return n; });
  const canFinish = Object.entries(perms).length > 0 && Object.entries(perms).every(([s, r]) => r.passed || skipped.has(s));

  const finish = async () => {
    setLoading(true); setError(null);
    if (skipped.size) {
      await fetch('/api/init/skip-services', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ services: [...skipped] }),
      });
    }
    const r = await fetch('/api/init/complete', { method: 'POST' });
    const result = await r.json();
    setLoading(false);
    if (result.initialized) setStep(3);
    else setError(result.error || 'Setup failed.');
  };

  const policyText = `cloudwatch:Describe*, cloudwatch:Get*
logs:Describe*, logs:Get*, logs:StartQuery, logs:GetQueryResults
cloudtrail:LookupEvents
ecs:List*, ecs:Describe*
lambda:List*, lambda:GetFunction*
ec2:Describe*
rds:Describe*
iam:Get*, iam:List*
sts:GetCallerIdentity
sns:Publish, sns:GetTopicAttributes
sqs:CreateQueue, sqs:SetQueueAttributes, sqs:GetQueueAttributes
sqs:ReceiveMessage, sqs:DeleteMessage, sqs:ListQueues
events:PutRule, events:PutTargets, events:ListRules
events:RemoveTargets, events:DeleteRule`;

  const copyPolicy = () => { navigator.clipboard.writeText(policyText); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  const passed = Object.values(perms).filter(r => r.passed).length;
  const total = Object.keys(perms).length;

  return (
    <div className="h-screen bg-white dark:bg-[#09090B] flex flex-col overflow-hidden">
      <header className="shrink-0 px-8 py-5 flex items-center gap-3">
        <div className="w-9 h-9 bg-gradient-to-br from-indigo-500 to-violet-600 rounded-xl flex items-center justify-center">
          <Terminal size={16} className="text-white" />
        </div>
        <span className="text-base font-semibold text-gray-900 dark:text-white">OpenDevOps</span>
      </header>

      <main className="flex-1 overflow-y-auto px-6 pb-16">
        <div className="w-full max-w-xl mx-auto pt-8">

          {/* Step dots */}
          <div className="flex items-center justify-center gap-2 mb-12">
            {STEPS.map((_, i) => (
              <div key={i} className={cn(
                'h-2 rounded-full transition-all duration-500',
                i === step ? 'w-8 bg-indigo-500' : i < step ? 'w-2 bg-emerald-500' : 'w-2 bg-gray-200 dark:bg-[#27272A]'
              )} />
            ))}
          </div>

          {/* Step 0: Account */}
          {step === 0 && (
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight mb-3">Create your account</h1>
              <p className="text-lg text-gray-500 dark:text-[#A1A1AA] mb-10 leading-relaxed">
                Set up the admin credentials you'll use to access the dashboard.
              </p>
              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-[#D4D4D8] mb-2">Username</label>
                  <input value={username} onChange={e => setUsername(e.target.value)} placeholder="admin" className={inp} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-[#D4D4D8] mb-2">Password</label>
                  <div className="relative">
                    <input type={showPw ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)}
                      placeholder="At least 6 characters" className={inp + ' pr-11'} />
                    <button type="button" onClick={() => setShowPw(p => !p)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-white transition-colors">
                      {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>
              </div>
              {userError && <p className="mt-4 text-sm text-red-500">{userError}</p>}
              <button onClick={createUser} disabled={loading}
                className="w-full mt-10 flex items-center justify-center gap-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 text-base font-semibold py-4 rounded-xl hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50">
                {loading ? <Loader2 size={18} className="animate-spin" /> : <>Create & continue <ArrowRight size={16} /></>}
              </button>
            </div>
          )}

          {/* Step 1: Notifications */}
          {step === 1 && (
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight mb-3">Where should we send alerts?</h1>
              <p className="text-lg text-gray-500 dark:text-[#A1A1AA] mb-10 leading-relaxed">
                The agent publishes root-cause reports to SNS. Leave blank to skip.
              </p>
              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-[#D4D4D8] mb-2">SNS Topic ARN</label>
                  <input value={snsArn} onChange={e => handleSns(e.target.value)}
                    placeholder="arn:aws:sns:us-east-1:123456789012:alerts" className={inp} />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700 dark:text-[#D4D4D8]">AWS Region</label>
                    {region && snsArn.includes(region) && (
                      <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                        <CheckCircle size={12} /> Auto-detected
                      </span>
                    )}
                  </div>
                  <input value={region} onChange={e => setRegion(e.target.value)} placeholder="us-east-1" className={inp} />
                </div>
              </div>
              <button onClick={saveAndNext} disabled={loading}
                className="w-full mt-10 flex items-center justify-center gap-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 text-base font-semibold py-4 rounded-xl hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50">
                {loading ? <Loader2 size={18} className="animate-spin" /> : <>Continue <ArrowRight size={16} /></>}
              </button>
            </div>
          )}

          {/* Step 2: Permissions */}
          {step === 2 && (
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight mb-3">Verify AWS access</h1>
              <p className="text-lg text-gray-500 dark:text-[#A1A1AA] mb-10 leading-relaxed">One read call per service to confirm IAM permissions.</p>

              <details className="mb-8">
                <summary className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 dark:text-[#71717A] cursor-pointer hover:text-gray-700 dark:hover:text-[#A1A1AA]">
                  <Shield size={14} /> View required IAM permissions
                </summary>
                <div className="mt-4 relative">
                  <button onClick={copyPolicy} className="absolute top-3 right-3 p-2 rounded-lg bg-white/90 dark:bg-[#27272A] border border-gray-200 dark:border-[#3F3F46] text-gray-500 hover:text-gray-900 dark:hover:text-white transition-colors">
                    {copied ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
                  </button>
                  <pre className="bg-gray-50 dark:bg-[#18181B] rounded-xl border border-gray-200 dark:border-[#27272A] p-5 font-mono text-sm text-gray-600 dark:text-[#A1A1AA] overflow-x-auto whitespace-pre leading-relaxed">{policyText}</pre>
                </div>
              </details>

              {total === 0 && !checking && (
                <button onClick={checkPerms} className="w-full flex items-center justify-center gap-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 text-base font-semibold py-4 rounded-xl hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors">
                  <Shield size={16} /> Run checks
                </button>
              )}

              {checking && (
                <div className="flex flex-col items-center gap-4 py-16">
                  <Loader2 size={28} className="animate-spin text-indigo-500" />
                  <span className="text-base text-gray-500 dark:text-[#71717A]">Checking permissions…</span>
                </div>
              )}

              {total > 0 && !checking && (
                <>
                  <div className="flex items-center gap-4 mb-6">
                    <div className="flex-1 h-2.5 bg-gray-100 dark:bg-[#27272A] rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-500 rounded-full transition-all duration-700" style={{ width: `${(passed / total) * 100}%` }} />
                    </div>
                    <span className="text-sm font-semibold text-gray-600 dark:text-[#A1A1AA] tabular-nums">{passed}/{total}</span>
                  </div>

                  <div className="rounded-xl border border-gray-200 dark:border-[#27272A] overflow-hidden divide-y divide-gray-100 dark:divide-[#27272A]">
                    {Object.entries(perms).map(([svc, r]) => (
                      <div key={svc} className={cn('flex items-center gap-4 px-5 py-4', skipped.has(svc) && 'opacity-40')}>
                        <div className="shrink-0">
                          {r.passed ? <CheckCircle size={18} className="text-emerald-500" /> :
                           r.passed === null ? <AlertTriangle size={18} className="text-amber-500" /> :
                           skipped.has(svc) ? <SkipForward size={18} className="text-gray-400" /> :
                           <XCircle size={18} className="text-red-500" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className={cn('text-sm font-semibold', skipped.has(svc) ? 'line-through text-gray-400' : 'text-gray-900 dark:text-white')}>{SVC[svc]?.label || svc}</span>
                          <span className="text-sm text-gray-400 dark:text-[#52525B] ml-2">{SVC[svc]?.desc}</span>
                          {!r.passed && r.error && !skipped.has(svc) && <p className="text-xs text-red-500 truncate mt-1">{r.error}</p>}
                        </div>
                        {!r.passed && (
                          <button onClick={() => toggle(svc)} className="text-xs font-medium px-3 py-1.5 rounded-lg border border-gray-200 dark:border-[#3F3F46] text-gray-500 dark:text-[#A1A1AA] hover:bg-gray-50 dark:hover:bg-[#27272A] transition-colors">
                            {skipped.has(svc) ? 'Unskip' : 'Skip'}
                          </button>
                        )}
                      </div>
                    ))}
                  </div>

                  {error && (
                    <div className="mt-6 bg-red-50 dark:bg-red-500/5 border border-red-200 dark:border-red-500/20 rounded-xl p-5">
                      <p className="text-sm font-semibold text-red-700 dark:text-red-400 mb-1">Setup failed</p>
                      <p className="text-sm text-red-600 dark:text-red-400/80 font-mono break-all">{error}</p>
                    </div>
                  )}

                  <div className="flex gap-3 mt-8">
                    <button onClick={() => setStep(1)} className="flex items-center justify-center w-12 h-12 text-gray-500 dark:text-[#71717A] border border-gray-200 dark:border-[#27272A] rounded-xl hover:bg-gray-50 dark:hover:bg-[#18181B] transition-colors">
                      <ArrowLeft size={18} />
                    </button>
                    <button onClick={checkPerms} className="flex items-center gap-2 px-5 py-3 text-sm font-semibold text-gray-600 dark:text-[#A1A1AA] border border-gray-200 dark:border-[#27272A] rounded-xl hover:bg-gray-50 dark:hover:bg-[#18181B] transition-colors">Re-check</button>
                    <button onClick={finish} disabled={!canFinish || loading} className="flex-1 flex items-center justify-center gap-2 bg-emerald-600 text-white text-base font-semibold py-3.5 rounded-xl hover:bg-emerald-700 transition-colors disabled:opacity-40">
                      {loading ? <Loader2 size={18} className="animate-spin" /> : <>Finish setup <ArrowRight size={16} /></>}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Step 3: Ready */}
          {step === 3 && (
            <div className="text-center pt-8">
              <div className="w-20 h-20 bg-gradient-to-br from-emerald-400 to-emerald-600 rounded-3xl flex items-center justify-center mx-auto mb-8 shadow-xl shadow-emerald-500/20">
                <Zap size={36} className="text-white" />
              </div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight mb-3">You're all set</h1>
              <p className="text-lg text-gray-500 dark:text-[#A1A1AA] mb-12 max-w-sm mx-auto leading-relaxed">
                Your agent is ready to investigate AWS incidents in real time.
              </p>
              <button onClick={() => navigate('/', { replace: true })}
                className="inline-flex items-center gap-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 text-base font-semibold px-8 py-4 rounded-xl hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors">
                Open Dashboard <ArrowRight size={16} />
              </button>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}
