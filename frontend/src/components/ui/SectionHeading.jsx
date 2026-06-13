import Eyebrow from './Eyebrow.jsx'

export default function SectionHeading({
  eyebrow,
  title,
  lede,
  align = 'center',
  className = '',
  titleClassName = '',
  ledeClassName = '',
}) {
  const alignCls = align === 'left' ? 'text-left items-start' : 'text-center items-center'
  return (
    <div className={['flex flex-col gap-4', alignCls, className].filter(Boolean).join(' ')}>
      {eyebrow && <Eyebrow dot>{eyebrow}</Eyebrow>}
      {title && (
        <h2
          className={[
            'font-display text-h2 md:text-h1 text-navy tracking-tight text-balance',
            titleClassName,
          ].filter(Boolean).join(' ')}
        >
          {title}
        </h2>
      )}
      {lede && (
        <p
          className={[
            'text-body text-navy/65 max-w-[60ch]',
            align === 'center' ? 'mx-auto' : '',
            ledeClassName,
          ].filter(Boolean).join(' ')}
        >
          {lede}
        </p>
      )}
    </div>
  )
}
