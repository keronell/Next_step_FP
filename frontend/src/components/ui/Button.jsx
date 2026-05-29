import { Loader2 } from 'lucide-react'
import { motion } from 'framer-motion'
import { cn } from '../../lib/utils'

const VARIANT = {
  // Premium animated gold button: panning gradient + shimmer sweep + glow ring
  primary:
    'group relative overflow-hidden rounded-full text-navy font-semibold ' +
    'bg-[linear-gradient(110deg,var(--color-gold),45%,var(--color-gold-light),55%,var(--color-gold))] ' +
    'bg-[length:200%_100%] shadow-[0_8px_24px_-6px_rgba(201,168,76,0.5)] ' +
    'hover:shadow-[0_12px_32px_-4px_rgba(201,168,76,0.6)] ring-1 ring-inset ring-white/30',
  secondary:
    'group relative overflow-hidden rounded-full border border-gold/45 bg-cream/40 text-navy ' +
    'backdrop-blur-sm hover:border-gold hover:bg-gold/[0.07] transition-colors duration-base',
  ghost:
    'group relative rounded-full text-ink-soft hover:text-ink transition-colors duration-base',
}

const SIZE = {
  md: 'px-5 py-2.5 text-small',
  lg: 'px-8 py-4 text-body font-bold',
}

export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  className = '',
  children,
  as: Tag = 'button',
  ...rest
}) {
  const isDisabled = loading || disabled
  const cls = cn(
    'inline-flex items-center justify-center gap-2 focus-ring select-none',
    'transition-[background-position,box-shadow,border-color,color] duration-500',
    VARIANT[variant] || VARIANT.primary,
    SIZE[size] || SIZE.md,
    variant === 'primary' && 'hover:bg-[position:100%_0]',
    isDisabled && 'opacity-60 cursor-not-allowed pointer-events-none',
    className,
  )

  // Use framer-motion for string tags ('button' | 'a'); plain Tag otherwise.
  const MotionTag = typeof Tag === 'string' ? motion[Tag] : Tag
  const motionProps =
    typeof Tag === 'string' && !isDisabled
      ? { whileHover: { y: -2 }, whileTap: { scale: 0.97 } }
      : {}

  return (
    <MotionTag
      className={cls}
      disabled={Tag === 'button' ? isDisabled : undefined}
      {...motionProps}
      {...rest}
    >
      {/* Shimmer sweep (primary + secondary) */}
      {variant !== 'ghost' && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -translate-x-full bg-[linear-gradient(105deg,transparent_40%,rgba(255,255,255,0.45)_50%,transparent_60%)] transition-transform duration-700 ease-out group-hover:translate-x-full"
        />
      )}
      <span className="relative z-10 inline-flex items-center gap-2">
        {loading && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
        {children}
      </span>
    </MotionTag>
  )
}
