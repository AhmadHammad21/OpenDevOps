interface Props {
  sessionId: string;
}

export default function Header({ sessionId }: Props) {
  return (
    <header>
      <div className="logo">
        <div className="logo-icon">⚡</div>
        <h1>OpenDevOps Agent</h1>
        <span className="badge">BETA</span>
      </div>
      <span id="session-label">{sessionId.slice(0, 8)}</span>
    </header>
  );
}
