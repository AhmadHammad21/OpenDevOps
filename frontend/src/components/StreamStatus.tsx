interface Props {
  label: string;
}

export default function StreamStatus({ label }: Props) {
  return (
    <div className="flex items-center gap-2 pb-1.5 pl-10 text-xs text-gray-400 dark:text-[#64748B] italic">
      <div className="spinner-dots">
        <span /><span /><span />
      </div>
      <span>{label}</span>
    </div>
  );
}
