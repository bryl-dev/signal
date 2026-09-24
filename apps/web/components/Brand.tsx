export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-8 w-8 items-center justify-center rounded-full border border-signal-400/40 bg-signal-400/10 text-signal-400">
        <span className="h-2 w-2 rounded-full bg-signal-400 shadow-[0_0_12px_#e4b44c]" />
      </span>
      <div>
        <p className="font-display text-xl tracking-tight text-paper-50">Signal</p>
        {!compact ? (
          <p className="text-[11px] uppercase tracking-[0.18em] text-paper-400">
            Personal intelligence
          </p>
        ) : null}
      </div>
    </div>
  );
}
