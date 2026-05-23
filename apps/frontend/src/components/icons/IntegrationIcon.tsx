interface IconProps {
  size?: number;
  className?: string;
}

export function SlackIcon({ size = 16, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} aria-label="Slack">
      {/* top-left: pink */}
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52z" fill="#E01E5A"/>
      <path d="M6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#E01E5A"/>
      {/* top-right: green */}
      <path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834z" fill="#36C5F0"/>
      <path d="M8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill="#36C5F0"/>
      {/* bottom-right: yellow */}
      <path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834z" fill="#2EB67D"/>
      <path d="M17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312z" fill="#2EB67D"/>
      {/* bottom-left: blue */}
      <path d="M15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52z" fill="#ECB22E"/>
      <path d="M15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" fill="#ECB22E"/>
    </svg>
  );
}

export function TelegramIcon({ size = 16, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} aria-label="Telegram">
      <circle cx="12" cy="12" r="12" fill="#26A5E4"/>
      <path d="M5.172 11.688 17.14 7.098c.561-.203 1.051.137.869.988l-2.017 9.504c-.148.672-.543.836-1.1.52l-2.992-2.205-1.445 1.39c-.16.16-.295.295-.605.295l.215-3.047 5.543-5.008c.24-.215-.053-.334-.375-.119L6.844 13.65 3.89 12.762c-.664-.207-.676-.664.28-1.074z" fill="white"/>
    </svg>
  );
}

export function GitHubIcon({ size = 16, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className} aria-label="GitHub">
      <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
    </svg>
  );
}

export function PagerDutyIcon({ size = 16, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} aria-label="PagerDuty">
      <rect width="24" height="24" rx="4" fill="#06AC38"/>
      <path d="M10.5 16.5H8.25V19.5H10.5V16.5Z" fill="white"/>
      <path d="M10.5 4.5H7.5C6.675 4.5 6 5.175 6 6V14.25C6 15.075 6.675 15.75 7.5 15.75H10.5C12.984 15.75 15 13.734 15 11.25V9C15 6.516 12.984 4.5 10.5 4.5ZM10.5 13.5H8.25V6.75H10.5C11.742 6.75 12.75 7.758 12.75 9V11.25C12.75 12.492 11.742 13.5 10.5 13.5Z" fill="white"/>
    </svg>
  );
}

export function DatadogIcon({ size = 16, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} aria-label="Datadog">
      <rect width="24" height="24" rx="4" fill="#632CA6"/>
      <path d="M13.17 6.38 11.9 5.7l-3.84 2.08v4.1l1.27.69 3.84-2.08V6.38zm-1.27 3.5-1.3-.7V7.5l1.3.7v1.68zm1.27 1.02-1.27.7V9.92l1.27-.7v1.68z" fill="white"/>
      <path d="m15.71 9.17-1.27-.7v4.1l-3.84 2.08v1.38l5.11-2.77V9.17z" fill="white"/>
      <path d="M8.06 13.27v-1.38L6.79 11.2v4.1l5.11 2.77v-1.38l-3.84-2.08v-1.34z" fill="white"/>
    </svg>
  );
}

export function SnsIcon({ size = 16, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} aria-label="SNS">
      <rect width="24" height="24" rx="4" fill="#FF9900"/>
      <path d="M12 5a1 1 0 0 1 1 1v.27A5 5 0 0 1 17 11v3l1.707 1.707A1 1 0 0 1 18 17.5H6a1 1 0 0 1-.707-1.707L7 14v-3a5 5 0 0 1 4-4.9V6a1 1 0 0 1 1-1zm0 14a2 2 0 0 1-2-2h4a2 2 0 0 1-2 2z" fill="white"/>
    </svg>
  );
}

export function EmailIcon({ size = 16, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} aria-label="Email">
      <rect width="24" height="24" rx="4" fill="#6B7280"/>
      <path d="M4 8a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V8zm2.2 0 5.8 4 5.8-4H6.2zm11.8 1.5-5.4 3.73a1 1 0 0 1-1.2 0L6 9.5V16h12V9.5z" fill="white"/>
    </svg>
  );
}

const ICONS: Record<string, (props: IconProps) => JSX.Element> = {
  slack:     SlackIcon,
  telegram:  TelegramIcon,
  github:    GitHubIcon,
  pagerduty: PagerDutyIcon,
  datadog:   DatadogIcon,
  sns:       SnsIcon,
  email:     EmailIcon,
};

export function IntegrationIcon({ name, size = 16, className }: IconProps & { name: string }) {
  const Icon = ICONS[name.toLowerCase()];
  if (!Icon) return null;
  return <Icon size={size} className={className} />;
}
