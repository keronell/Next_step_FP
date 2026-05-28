import { useEffect, useRef } from 'react'
import { Sparkles, ArrowDown } from 'lucide-react'
import { useReveal } from '../hooks/useReveal'

function Hero({ onStart }) {
  const revealRef = useReveal(0.05)
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let animId
    let particles = []

    const resize = () => {
      canvas.width = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
      particles = Array.from({ length: 80 }, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.28,
        vy: (Math.random() - 0.5) * 0.28,
        r: Math.random() * 1.4 + 0.4,
        alpha: Math.random() * 0.35 + 0.1,
        gold: Math.random() < 0.15,
      }))
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
          : `rgba(160,190,210,${p.alpha * 0.45})`
        ctx.fill()
      })
      animId = requestAnimationFrame(draw)
    }

    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (!mq.matches) {
      resize()
      draw()
    }
    window.addEventListener('resize', resize)
    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [])

  const handleStart = () => {
    onStart()
    document.getElementById('assessment')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <section id="hero" className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden px-6 pt-8 pb-24">
      {/* Particle canvas */}
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" />

      {/* Soft gradient mesh */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-cream via-cream to-[#F0EAD8] opacity-60" />

      {/* Content */}
      <div ref={revealRef} className="reveal relative z-10 flex flex-col items-center text-center max-w-4xl">
        {/* Eyebrow */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-gold/10 border border-gold/30 mb-8">
          <Sparkles size={13} className="text-gold" />
          <span className="font-body text-xs font-semibold text-gold tracking-wider uppercase">
            Career Discovery Platform
          </span>
        </div>

        {/* Headline */}
        <h1 className="font-display font-bold text-5xl sm:text-6xl md:text-7xl lg:text-8xl text-navy leading-[1.08] tracking-tight mb-6">
          Discover Your
          <br />
          <span className="italic text-gold relative inline-block">
            Next Step
            <span className="gold-underline" />
          </span>
        </h1>

        {/* Subtext */}
        <p className="font-body text-lg sm:text-xl text-navy/60 max-w-xl leading-relaxed mb-10">
          Answer 10 thoughtful questions and get matched with your ideal tech career — plus a clear, personalized learning roadmap to get there.
        </p>

        {/* CTA */}
        <div className="flex flex-col sm:flex-row items-center gap-4">
          <button
            onClick={handleStart}
            className="btn-gold btn-gold-pulse px-8 py-4 rounded-full text-base font-semibold font-body flex items-center gap-2 min-w-[200px] justify-center"
          >
            <Sparkles size={16} />
            Start Assessment
          </button>
          <button
            onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}
            className="font-body text-sm text-navy/50 hover:text-navy transition-colors flex items-center gap-1.5 group"
          >
            See how it works
            <ArrowDown size={14} className="group-hover:translate-y-0.5 transition-transform" />
          </button>
        </div>

        {/* Social proof */}
        <div className="mt-14 flex items-center gap-6 opacity-50">
          <div className="flex -space-x-2">
            {['#C9A84C', '#1A2D47', '#C9A84C'].map((bg, i) => (
              <div
                key={i}
                className="w-8 h-8 rounded-full border-2 border-cream flex items-center justify-center text-xs font-bold text-cream"
                style={{ background: bg }}
              >
                {String.fromCharCode(65 + i)}
              </div>
            ))}
          </div>
          <p className="font-body text-sm text-navy/50">
            Join thousands of tech learners finding their path
          </p>
        </div>
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 opacity-30">
        <div className="w-px h-12 bg-gradient-to-b from-transparent via-navy to-transparent" />
        <ArrowDown size={14} className="text-navy animate-bounce" />
      </div>
    </section>
  )
}

export default Hero
