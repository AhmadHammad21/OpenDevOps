interface Props {
  content: string;
}

export default function UserMessage({ content }: Props) {
  return (
    <div className="flex flex-col items-end gap-1.5">
      <div className="flex flex-row-reverse gap-2.5 items-start max-w-[780px]">
        <div className="w-[30px] h-[30px] rounded-lg flex items-center justify-center text-sm shrink-0 mt-0.5 bg-blue-900/60 select-none">
          👤
        </div>
        <div className="px-3.5 py-2.5 rounded-xl rounded-br-sm text-sm leading-relaxed break-words max-w-[680px] bg-blue-900/50 border border-blue-500/25">
          {content}
        </div>
      </div>
    </div>
  );
}
