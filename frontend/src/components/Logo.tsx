/** Original SourceAtlas mark: a compass rose whose needle points to a cited source. */
export function LogoMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <circle cx="16" cy="16" r="14" fill="var(--indigo)" />
      <circle cx="16" cy="16" r="10.5" stroke="var(--sand)" strokeWidth="1" opacity="0.7" />
      <path d="M16 6 L19 16 L16 26 L13 16 Z" fill="var(--paper)" opacity="0.95" />
      <path d="M16 6 L19 16 L16 16 Z" fill="var(--teal)" />
      <circle cx="16" cy="16" r="1.8" fill="var(--indigo)" stroke="var(--paper)" strokeWidth="1" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark />
      <span className="font-serif text-xl tracking-tight">Source<em className="text-teal not-italic">Atlas</em></span>
    </span>
  );
}
