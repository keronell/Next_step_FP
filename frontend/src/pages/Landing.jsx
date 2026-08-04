import { useState } from 'react'
import { Sparkles, ArrowDown, Lock } from 'lucide-react'
import { motion } from 'framer-motion'
import Button from '../components/ui/Button.jsx'
import ParticleField from '../components/ParticleField'
import { useAuth } from '../contexts/AuthContext'

const container = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.12, delayChildren: 0.1 },
  },
}

const item = {
  hidden: { opacity: 0, y: 28, filter: 'blur(6px)' },
  show: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { duration: 0.7, ease: [0.25, 0.46, 0.45, 0.94] },
  },
}

function Hero({ onStart }) {
  const [pulseOn, setPulseOn] = useState(true)
  const { user, authLoading } = useAuth()
  const isLocked = !authLoading && !user

  const handleStart = () => {
    setPulseOn(false)
    onStart()
    document.getElementById('assessment')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <section id="hero" className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden px-6 pt-8 pb-24">
      {/* Aurora gradient background. DEV-80: three blurred blobs used to sit on top of
          this gradient, but they never rendered — they tinted with `bg-gold/25` etc., and
          the theme tokens are bare `var(--color-*)` strings with no `<alpha-value>`, so
          Tailwind silently emits no utility for an alpha modifier (see frontend/CLAUDE.md).
          Removed rather than repaired, to keep this hero and the roadmap hero identical. */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-cream via-cream to-[#F0EAD8]" />
      </div>

      {/* Particle canvas. Shared with the roadmap page's hero band — the defaults
          are this hero's original counts, so nothing here changed. */}
      <ParticleField />

      {/* Content */}
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="relative z-10 flex flex-col items-center text-center max-w-4xl"
      >
        {/* Headline */}
        <motion.h1
          variants={item}
          className="font-display font-bold text-display text-navy tracking-tight text-balance mb-6"
        >
          Discover Your
          <br />
          <span className="italic text-gold relative inline-block">
            Next Step
            <motion.span
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ delay: 0.9, duration: 0.8, ease: [0.25, 0.46, 0.45, 0.94] }}
              className="absolute -bottom-1 left-0 right-0 h-[2px] origin-left bg-gradient-to-r from-transparent via-gold to-transparent"
            />
          </span>
        </motion.h1>

        {/* Subtext */}
        <motion.p
          variants={item}
          className="font-body text-body text-navy/65 max-w-[52ch] leading-snug mb-10"
        >
          Up to 15 questions · 3-5 minutes. Get matched with your ideal tech career - plus a personalized roadmap to get there.
        </motion.p>

        {/* CTA */}
        <motion.div variants={item} className="flex flex-col sm:flex-row items-center gap-4">
          <Button
            variant="primary"
            size="lg"
            onClick={handleStart}
            className={`${pulseOn && !isLocked ? 'btn-gold-pulse' : ''} min-w-[200px]`}
          >
            {isLocked ? (
              <>
                <Lock size={16} aria-hidden="true" />
                Sign in to Start
              </>
            ) : (
              <>
                <Sparkles size={16} aria-hidden="true" />
                Start Assessment
              </>
            )}
          </Button>
          <Button
            variant="ghost"
            size="md"
            onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}
            className="group !px-3"
          >
            See how it works
            <ArrowDown size={14} className="group-hover:translate-y-0.5 transition-transform" aria-hidden="true" />
          </Button>
        </motion.div>

        {/* Social proof */}
        <motion.div variants={item} className="mt-14 flex flex-col items-center gap-3">
          <div className="flex items-center gap-4 opacity-70">
            <div className="flex -space-x-2">
              {['var(--color-gold)', 'var(--color-navy-light)', 'var(--color-gold)'].map((bg, i) => (
                <div
                  key={i}
                  className="w-8 h-8 rounded-full border-2 border-cream flex items-center justify-center text-xs font-bold text-cream"
                  style={{ background: bg }}
                >
                  {String.fromCharCode(65 + i)}
                </div>
              ))}
            </div>
            <p className="font-body text-small text-navy/55">
              <span className="tabular font-semibold text-navy/75">2,400+</span> learners finding their path
            </p>
          </div>
        </motion.div>
      </motion.div>

      {/* Scroll indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 opacity-40">
        <div className="w-px h-12 bg-gradient-to-b from-transparent via-navy to-transparent" />
        <ArrowDown size={14} className="text-navy animate-bounce" aria-hidden="true" />
      </div>
    </section>
  )
}

export default Hero
