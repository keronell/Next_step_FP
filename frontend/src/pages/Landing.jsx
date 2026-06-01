import { useEffect, useRef, useState } from 'react'
import { Sparkles, ArrowDown } from 'lucide-react'
import { motion } from 'framer-motion'
import Button from '../components/ui/Button.jsx'
import Badge from '../components/ui/Badge.jsx'
import Eyebrow from '../components/ui/Eyebrow.jsx'

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
  const canvasRef = useRef(null)
  const [pulseOn, setPulseOn] = useState(true)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (mq.matches) return

    const ctx = canvas.getContext('2d')
    let animId
    let particles = []
    let started = false

    const seed = (w, h) => {
      const count = window.innerWidth < 640 ? 28 : 80
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.28,
        vy: (Math.random() - 0.5) * 0.28,
        r: Math.random() * 2.2 + 1.3,
        alpha: Math.random() * 0.4 + 0.4,
        gold: Math.random() < 0.4,
      }))
    }

    const resize = () => {
      const w = canvas.offsetWidth
      const h = canvas.offsetHeight
      if (w === 0 || h === 0) return // not laid out yet — wait for the observer
      canvas.width = w
      canvas.height = h
      seed(w, h)
      if (!started) {
        started = true
        draw()
      }
    }

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      particles.forEach(p => {
        p.x += p.vx
        p.y += p.vy
        if (p.x < 0) p.x = canvas.width
        if (p.x > canvas.width) p.x = 0
        if (p.y < 0) p.y = canvas.height
        if (p.y > canvas.height) p.y = 0
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = p.gold
          ? `rgba(201,168,76,${p.alpha})`
          : `rgba(40,58,90,${p.alpha * 0.7})`
        ctx.fill()
      })
      animId = requestAnimationFrame(draw)
    }

    // ResizeObserver fires as soon as the canvas has a real size (and on any
    // later size change), so it doesn't matter when layout/fonts settle.
    const observer = new ResizeObserver(resize)
    observer.observe(canvas)
    resize() // also try immediately in case it's already sized

    return () => {
      cancelAnimationFrame(animId)
      observer.disconnect()
    }
  }, [])

  const handleStart = () => {
    setPulseOn(false)
    onStart()
    document.getElementById('assessment')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <section id="hero" className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden px-6 pt-8 pb-24">
      {/* Aurora gradient background */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-cream via-cream to-[#F0EAD8]" />
        <div className="absolute -top-1/4 left-[15%] h-[30rem] w-[30rem] rounded-full bg-gold/25 opacity-60 blur-3xl animate-aurora-1" />
        <div className="absolute top-[10%] right-[10%] h-[26rem] w-[26rem] rounded-full bg-gold-light/25 opacity-50 blur-3xl animate-aurora-2" />
        <div className="absolute -bottom-1/4 left-[30%] h-[28rem] w-[28rem] rounded-full bg-navy/10 opacity-40 blur-3xl animate-aurora-1 [animation-delay:6s]" />
      </div>

      {/* Particle canvas */}
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" />

      {/* Content */}
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="relative z-10 flex flex-col items-center text-center max-w-4xl"
      >
        {/* Eyebrow badge */}
        <motion.div variants={item}>
          <Badge tone="gold" icon={Sparkles} className="mb-8 border-gold/40">
            Career Discovery Platform
          </Badge>
        </motion.div>

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
          Answer 10 thoughtful questions and get matched with your ideal tech career — plus a clear, personalized learning roadmap to get there.
        </motion.p>

        {/* CTA */}
        <motion.div variants={item} className="flex flex-col sm:flex-row items-center gap-4">
          <Button
            variant="primary"
            size="lg"
            onClick={handleStart}
            className={`${pulseOn ? 'btn-gold-pulse' : ''} min-w-[200px]`}
          >
            <Sparkles size={16} aria-hidden="true" />
            Start Assessment
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
          <Eyebrow dot>Trusted by</Eyebrow>
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
