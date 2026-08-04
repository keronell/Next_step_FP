// Drifting particle canvas — the gold/navy dot field behind a hero. Lifted out of
// Landing.jsx so the roadmap page's hero band can wear the same effect (DEV-80).
//
// `count`/`countSmall` default to Landing's original values; a shorter hero passes
// fewer so the dots don't read denser (the call site explains its own sizing).
// `style` is how a caller adds a mask fade.
//
// The dot colors are literal rgba, not theme tokens — canvas can't read CSS vars,
// so a theme change will NOT move them. Note the navy here (#283A5A) is its own
// shade, matching neither --color-navy (#0F1B2D) nor --color-navy-light (#1A2D47);
// it predates the extraction and is kept as-is to leave the Landing hero unchanged.
import { useEffect, useRef } from 'react'

export default function ParticleField({ count = 80, countSmall = 28, style }) {
  const canvasRef = useRef(null)

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
      const n = window.innerWidth < 640 ? countSmall : count
      particles = Array.from({ length: n }, () => ({
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
      if (w === 0 || h === 0) return // not laid out yet - wait for the observer
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
  }, [count, countSmall])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={style}
      className="absolute inset-0 w-full h-full pointer-events-none"
    />
  )
}
