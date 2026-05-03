const CHIPS = [
  'Show CloudWatch alarms in ALARM state',
  'What AWS API calls happened in the last hour?',
  'Show Lambda errors in the last 2 hours',
  'Check ECS service health in default cluster',
  'Any deployments or config changes recently?',
  'Why is my Lambda throttling?',
  'Which alarms have been investigated most in the last 30 days?',
  'What recurring errors have we seen across past investigations?',
  'Search past investigations for Lambda throttling',
];

interface Props {
  onChip: (text: string) => void;
}

export default function EmptyState({ onChip }: Props) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6 py-8">
      <div className="w-[52px] h-[52px] bg-indigo-50 dark:bg-[#1E1B4B] rounded-2xl flex items-center justify-center text-2xl select-none">
        ⚡
      </div>
      <div className="text-center">
        <h2 className="text-[18px] font-semibold text-gray-900 dark:text-[#F1F5F9] mb-1.5">OpenDevOps Agent</h2>
        <p className="text-[13px] text-gray-500 dark:text-[#94A3B8] max-w-[360px] leading-relaxed">
          Ask about your AWS infrastructure or describe an incident.
        </p>
      </div>
      <div className="flex flex-wrap gap-2 justify-center mt-1">
        {CHIPS.map(chip => (
          <button
            key={chip}
            onClick={() => onChip(chip)}
            className="text-[12px] px-3 py-[5px] bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-full text-gray-500 dark:text-[#94A3B8] hover:text-indigo-500 dark:hover:text-[#818CF8] hover:border-indigo-200 dark:hover:border-[#3730A3] hover:bg-indigo-50 dark:hover:bg-[#1E1B4B] transition-all cursor-pointer"
          >
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}
