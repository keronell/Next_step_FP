export default function Card({
  accent = 'none',
  interactive = false,
  className = '',
  children,
  as: Tag = 'div',
  ...rest
}) {
  const cls = [
    'relative rounded-card bg-white/60 border border-navy/[0.06]',
    interactive ? 'card-hover' : '',
    accent === 'gold' ? 'pl-1' : '',
    className,
  ].filter(Boolean).join(' ')

  return (
    <Tag className={cls} {...rest}>
      {accent === 'gold' && (
        <span
          aria-hidden="true"
          className="absolute left-0 top-0 bottom-0 w-[3px] rounded-l-card bg-gold"
        />
      )}
      {children}
    </Tag>
  )
}
