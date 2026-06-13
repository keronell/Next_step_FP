const TONE = {
  gold: 'bg-gold/15 text-navy border border-gold/30',
  navy: 'bg-navy/10 text-navy border border-navy/20',
  neutral: 'bg-navy/[0.04] text-navy/70 border border-navy/10',
}

export default function Badge({
  tone = 'gold',
  icon: Icon = null,
  className = '',
  children,
  ...rest
}) {
  const cls = [
    'inline-flex items-center gap-1.5',
    'rounded-full px-3 py-1 text-eyebrow uppercase',
    TONE[tone] || TONE.gold,
    className,
  ].filter(Boolean).join(' ')

  return (
    <span className={cls} {...rest}>
      {Icon && <Icon size={13} aria-hidden="true" />}
      {children}
    </span>
  )
}
