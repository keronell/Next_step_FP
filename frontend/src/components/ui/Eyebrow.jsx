export default function Eyebrow({ dot = false, className = '', children, ...rest }) {
  const cls = [
    'inline-flex items-center gap-2',
    'text-eyebrow uppercase font-medium text-navy/70',
    className,
  ].filter(Boolean).join(' ')

  return (
    <span className={cls} {...rest}>
      {dot && (
        <span
          aria-hidden="true"
          className="inline-block h-1 w-1 rounded-full bg-gold"
        />
      )}
      {children}
    </span>
  )
}
