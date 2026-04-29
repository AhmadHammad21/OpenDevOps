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
    <div className="empty-state">
      <div className="es-icon">⚡</div>
      <h2>OpenDevOps Agent</h2>
      <p>Ask about your AWS infrastructure or describe an incident — I'll investigate using your live AWS data.</p>
      <div className="chips">
        {CHIPS.map(chip => (
          <span key={chip} className="chip" onClick={() => onChip(chip)}>
            {chip}
          </span>
        ))}
      </div>
    </div>
  );
}
