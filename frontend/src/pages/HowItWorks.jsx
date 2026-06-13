import { ClipboardList, BarChart3, Map } from 'lucide-react'
import { motion, useMotionValue, useMotionTemplate } from 'framer-motion'
import { useReveal } from '../hooks/useReveal'
import Badge from '../components/ui/Badge.jsx'
import SectionHeading from '../components/ui/SectionHeading.jsx'

const STEPS = [
  {
    number: '01',
    icon: ClipboardList,
    title: 'Answer 10 Questions',
    description: 'Tell us about your skills, interests, and work style through a quick, thoughtfully designed quiz.',
  },
  {
    number: '02',
    icon: BarChart3,
    title: 'Get Matched',
    description: 'Our scoring engine analyzes your answers and surfaces your top 3 tech career matches — with percentage fit.',
  },
  {
    number: '03',
    icon: Map,
    title: 'Follow Your Roadmap',
    description: 'Explore a visual learning tree for your chosen career, from beginner concepts to advanced mastery.',
  },
]

function HowItWorks() {
  const revealRef = useReveal(0.1)

  return (
    <section id="how-it-works" className="py-24 px-6 bg-navy/[0.03]">
      <div className="max-w-6xl mx-auto">
        <div ref={revealRef} className="reveal mb-16">
          <SectionHeading
            eyebrow="How It Works"
            title="Three steps to clarity"
            align="center"
          />
        </div>

        <div className="relative">
          {/* Connecting lines (desktop) */}
          <div className="hidden md:flex absolute top-[64px] left-0 right-0 items-center px-[calc(16.666%-24px)] pointer-events-none">
            <div
              className="flex-1 h-px line-reveal"
              style={{ background: 'linear-gradient(to right, color-mix(in srgb, var(--color-gold) 38%, transparent), var(--color-gold))' }}
            />
            <div className="w-8" />
            <div
              className="flex-1 h-px line-reveal"
              style={{ background: 'linear-gradient(to right, var(--color-gold), color-mix(in srgb, var(--color-gold) 38%, transparent))' }}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-12">
            {STEPS.map((step, i) => (
              <StepCard key={i} step={step} index={i} />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

function StepCard({ step, index }) {
  const Icon = step.icon
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)

  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    mouseX.set(e.clientX - rect.left)
    mouseY.set(e.clientY - rect.top)
  }

  const spotlight = useMotionTemplate`radial-gradient(240px circle at ${mouseX}px ${mouseY}px, rgba(201,168,76,0.16), transparent 80%)`

  return (
    <motion.div
      onMouseMove={handleMouseMove}
      initial={{ opacity: 0, y: 36 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.6, delay: index * 0.12, ease: [0.25, 0.46, 0.45, 0.94] }}
      whileHover={{ y: -6 }}
      className="group relative rounded-card overflow-hidden bg-cream border border-navy/[0.06] p-8 flex flex-col items-center text-center shadow-sm hover:shadow-[0_18px_44px_-16px_rgba(201,168,76,0.35)] hover:border-gold/40 transition-[box-shadow,border-color] duration-base"
    >
      {/* Mouse-follow spotlight */}
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{ background: spotlight }}
      />

      {/* Faint number watermark */}
      <span className="absolute top-2 left-4 font-display font-bold text-4xl text-navy/[0.06] select-none z-10" aria-hidden="true">
        {step.number}
      </span>

      <div className="relative z-10 flex flex-col items-center">
        {/* Step badge */}
        <Badge tone="gold" className="mb-5 border-gold/40">
          Step {step.number}
        </Badge>

        {/* Icon circle */}
        <div className="w-12 h-12 rounded-full flex items-center justify-center mb-5 bg-gold/12 border border-gold/30 transition-transform duration-base group-hover:scale-110 group-hover:rotate-6">
          <Icon size={22} className="text-gold" aria-hidden="true" />
        </div>

        <h3 className="font-display font-semibold text-h3 text-navy mb-3">
          {step.title}
        </h3>
        <p className="font-body text-body text-navy/65 leading-relaxed">
          {step.description}
        </p>

        {/* Step indicator dot */}
        <div className="mt-6 w-2 h-2 rounded-full bg-gold/60" aria-hidden="true" />
      </div>
    </motion.div>
  )
}

export default HowItWorks
