import { ClipboardList, BarChart3, Map } from 'lucide-react'
import { useReveal } from '../hooks/useReveal'

const STEPS = [
  {
    number: '01',
    icon: ClipboardList,
    title: 'Answer 10 Questions',
    description: 'Tell us about your skills, interests, and work style through a quick, thoughtfully designed quiz.',
    color: '#22C55E',
  },
  {
    number: '02',
    icon: BarChart3,
    title: 'Get Matched',
    description: 'Our scoring engine analyzes your answers and surfaces your top 3 tech career matches — with percentage fit.',
    color: '#C9A84C',
  },
  {
    number: '03',
    icon: Map,
    title: 'Follow Your Roadmap',
    description: 'Explore a visual learning tree for your chosen career, from beginner concepts to advanced mastery.',
    color: '#0F1B2D',
  },
]

function HowItWorks() {
  const revealRef = useReveal(0.1)

  return (
    <section id="how-it-works" className="py-24 px-6 bg-navy/[0.03]">
      <div className="max-w-6xl mx-auto">
        {/* Section header */}
        <div ref={revealRef} className="reveal text-center mb-16">
          <p className="font-body text-xs font-semibold text-gold tracking-widest uppercase mb-3">
            How It Works
          </p>
          <h2 className="font-display font-bold text-4xl md:text-5xl text-navy">
            Three steps to clarity
          </h2>
        </div>

        {/* Steps */}
        <StepsRow />
      </div>
    </section>
  )
}

function StepsRow() {
  const rowRef = useReveal(0.1)

  return (
    <div ref={rowRef} className="reveal-stagger reveal relative">
      {/* Connecting lines (desktop) */}
      <div className="hidden md:flex absolute top-[72px] left-0 right-0 items-center px-[calc(16.666%-24px)] pointer-events-none">
        <div className="flex-1 h-px line-reveal" style={{ background: 'linear-gradient(to right, #C9A84C60, #C9A84C)' }} />
        <div className="w-8" />
        <div className="flex-1 h-px line-reveal" style={{ background: 'linear-gradient(to right, #C9A84C, #C9A84C60)' }} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-12">
        {STEPS.map((step, i) => (
          <StepCard key={i} step={step} index={i} />
        ))}
      </div>
    </div>
  )
}

function StepCard({ step, index }) {
  const Icon = step.icon

  return (
    <div className="card-hover flex flex-col items-center text-center p-8 rounded-2xl bg-cream border border-navy/8 shadow-sm relative group">
      {/* Number badge */}
      <div className="absolute top-2 left-4 font-display font-bold text-4xl text-navy/5 select-none">
        {step.number}
      </div>

      {/* Icon circle */}
      <div
        className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5 transition-transform duration-300 group-hover:scale-110"
        style={{ background: `${step.color}15`, border: `1.5px solid ${step.color}30` }}
      >
        <Icon size={26} style={{ color: step.color }} />
      </div>

      <h3 className="font-display font-semibold text-xl text-navy mb-3">
        {step.title}
      </h3>
      <p className="font-body text-sm text-navy/55 leading-relaxed">
        {step.description}
      </p>

      {/* Step indicator dot */}
      <div
        className="mt-6 w-2 h-2 rounded-full opacity-60"
        style={{ background: step.color }}
      />
    </div>
  )
}

export default HowItWorks
