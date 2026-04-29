interface Props {
  label: string;
}

export default function StreamStatus({ label }: Props) {
  return (
    <div className="stream-status">
      <div className="spinner-dots">
        <span /><span /><span />
      </div>
      <span>{label}</span>
    </div>
  );
}
