const CHIPS = [
  'Why is my Lambda throttling?',
  'Show alarms in ALARM state',
  'Any deployments in the last 2 hours?',
  'High error rate on payment service',
  'Payment service ECS tasks are failing and Lambda errors are spiking — check service health, recent deployments, alarms, and logs',
];

interface Props {
  onChip: (text: string) => void;
}

export default function EmptyState({ onChip }: Props) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6">
      <div className="w-14 h-14 bg-gradient-to-br from-emerald-500 to-emerald-700 rounded-2xl flex items-center justify-center text-3xl select-none">
        ⚡
      </div>
      <div className="text-center">
        <h2 className="text-xl font-semibold text-gray-100 mb-1">OpenDevOps Agent</h2>
        <p className="text-sm text-gray-400 max-w-md leading-relaxed">
          Ask about your AWS infrastructure or describe an incident — I'll investigate using your live AWS data.
        </p>
      </div>
      <div className="flex flex-wrap gap-2 justify-center mt-1">
        {CHIPS.map(chip => (
          <button
            key={chip}
            onClick={() => onChip(chip)}
            className="text-xs px-3.5 py-1.5 bg-gray-800 border border-gray-700 rounded-full text-gray-400 hover:text-emerald-400 hover:border-emerald-500/50 hover:bg-emerald-500/5 transition-all cursor-pointer"
          >
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}
