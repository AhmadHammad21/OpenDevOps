interface Props {
  content: string;
}

export default function UserMessage({ content }: Props) {
  return (
    <div className="flex justify-end" style={{ animation: 'fadeIn 200ms ease' }}>
      <div className="max-w-[580px] bg-indigo-500 dark:bg-[#4F46E5] rounded-[10px] rounded-tr-[2px] px-3.5 py-2.5 text-[16px] text-white leading-relaxed break-words">
        {content}
      </div>
    </div>
  );
}
