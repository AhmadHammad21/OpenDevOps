interface Props {
  content: string;
}

export default function UserMessage({ content }: Props) {
  return (
    <div className="turn user">
      <div className="msg-row">
        <div className="avatar">👤</div>
        <div className="bubble">{content}</div>
      </div>
    </div>
  );
}
