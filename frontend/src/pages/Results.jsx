import { useEffect, useState } from 'react'
import { Monitor, Server, BarChart2, Layers, Compass, Pen, ChevronRight, Trophy, Medal, Award } from 'lucide-react'
import { motion } from 'framer-motion'
import { useReveal } from '../hooks/useReveal'
import Badge from '../components/ui/Badge.jsx'
import Button from '../components/ui/Button.jsx'
import SectionHeading from '../components/ui/SectionHeading.jsx'

const ICON_MAP = {
  Monitor, Server, BarChart2, Layers, Compass, Pen,
}

// Abstract-geometric illustrations (palette-locked), keyed by career id.
const CAREER_ART = {
  'frontend':        '/illustrations/career-frontend.png',
  'backend':         '/illustrations/career-backend.png',
  'data-science':    '/illustrations/career-data-science.png',
  'devops':          '/illustrations/career-devops.png',
  'product-manager': '/illustrations/career-product-manager.png',
  'ux-designer':     '/illustrations/career-ux-designer.png',
}

const RANK_STYLES = [
  { icon: Trophy, label: 'Best Match', tone: 'gold' },
  { icon: Medal,  label: 'Strong Match', tone: 'neutral' },
  { icon: Award,  label: 'Good Fit', tone: 'neutral' },
]

function Results({ phase, results, onSelectCareer, selectedCareer }) {
  const revealRef = useReveal(0.1)

  if (phase !== 'results_ready' || !results) return null

  return (
    <section id="results" className="py-24 px-6 bg-navy/[0.02]">
      <div className="max-w-6xl mx-auto">
        <div ref={revealRef} className="reveal mb-14">
          <SectionHeading
            eyebrow="Your Results"
            title="Your top career matches"
            lede="Based on your answers, here are the tech roles where you’re most likely to thrive."
            align="center"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {results.map((career, i) => (
            <CareerCard
              key={career.id}
              career={career}
              rank={i}
              isSelected={selectedCareer === career.id}
              onSelect={() => onSelectCareer(career.id)}
            />
          ))}
        </div>
      </div>
    </section>
  )
}

function CareerCard({ career, rank, isSelected, onSelect }) {
  const [displayPercent, setDisplayPercent] = useState(0)
  const rankStyle = RANK_STYLES[rank]
  const RankIcon = rankStyle.icon
  const CareerIcon = ICON_MAP[career.icon] || Monitor
  const art = CAREER_ART[career.id]

  useEffect(() => {
    let raf
    const timer = setTimeout(() => {
      const start = Date.now()
      const duration = 1100
      const target = career.matchPercent
      // Elastic-out style: 1 + c3*(t-1)^3 + c1*(t-1)^2 (Penner overshoot)
      const ease = (t) => {
        const c1 = 1.70158
        const c3 = c1 + 1
        return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2)
      }
      const tick = () => {
        const elapsed = Date.now() - start
        const progress = Math.min(elapsed / duration, 1)
        const eased = ease(progress)
        setDisplayPercent(Math.round(Math.max(0, eased) * target))
        if (progress < 1) raf = requestAnimationFrame(tick)
      }
      raf = requestAnimationFrame(tick)
    }, rank * 180)
    return () => { clearTimeout(timer); cancelAnimationFrame(raf) }
  }, [career.matchPercent, rank])

  const isTop = rank === 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.55, delay: rank * 0.12, ease: [0.25, 0.46, 0.45, 0.94] }}
      whileHover={{ y: -6 }}
      className={`group relative flex flex-col overflow-hidden rounded-card bg-white transition-[border-color,box-shadow] duration-base
        ${isSelected
          ? 'border border-gold shadow-lg shadow-gold/15 ring-2 ring-gold/30'
          : isTop
          ? 'border border-gold/30 shadow-sm hover:border-gold/55 hover:shadow-[0_20px_50px_-18px_rgba(201,168,76,0.45)]'
          : 'border border-navy/[0.08] shadow-sm hover:border-gold/40 hover:shadow-[0_16px_40px_-18px_rgba(15,27,45,0.25)]'
        }`}
    >
      {/* Best-match ambient glow */}
      {isTop && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-16 left-1/2 -translate-x-1/2 h-40 w-40 rounded-full bg-gold/25 blur-3xl opacity-60 group-hover:opacity-90 transition-opacity duration-base"
        />
      )}

      {/* Top accent bar — gold gradient on rank-1, soft neutral on others */}
      <div
        className="relative z-10 h-1 w-full"
        style={{
          background: isTop
            ? 'linear-gradient(to right, var(--color-gold-light), var(--color-gold))'
            : 'linear-gradient(to right, rgba(15,27,45,0.08), rgba(15,27,45,0.18))'
        }}
        aria-hidden="true"
      />

      <div className="relative z-10 p-6 flex flex-col flex-1">
        {/* Rank badge */}
        <Badge tone={rankStyle.tone} icon={RankIcon} className="self-start mb-4">
          {rankStyle.label}
        </Badge>

        {/* Career icon + Match % */}
        <div className="flex items-center justify-between mb-2">
          <div
            className={`w-14 h-14 rounded-xl overflow-hidden flex items-center justify-center transition-transform duration-base group-hover:scale-110
              ${isTop ? 'bg-gold/15 border border-gold/30' : 'bg-navy/[0.04] border border-navy/[0.08]'}`}
          >
            {art ? (
              <img
                src={art}
                alt={career.title}
                width={56}
                height={56}
                loading="lazy"
                className="w-full h-full object-cover"
              />
            ) : (
              <CareerIcon size={20} className={isTop ? 'text-gold' : 'text-navy/70'} aria-hidden="true" />
            )}
          </div>
          <div className="text-right">
            <span className="font-display font-bold text-h2 text-navy tabular">
              {displayPercent}
            </span>
            <span className="font-body text-h3 text-gold font-semibold">%</span>
          </div>
        </div>

        {/* Gradient match micro-bar */}
        <div className="h-1 bg-navy/[0.08] rounded-full overflow-hidden mb-4">
          <div
            className="h-full rounded-full bg-gradient-to-r from-gold to-gold-light transition-[width] ease-out"
            style={{ width: `${displayPercent}%`, transitionDuration: '700ms' }}
          />
        </div>

        {/* Title */}
        <h3 className="font-display font-semibold text-h3 text-navy mb-2 tracking-tight">
          {career.title}
        </h3>

        {/* Description */}
        <p className="font-body text-small text-navy/65 leading-relaxed mb-5 flex-1">
          {career.description}
        </p>

        {/* Key skills */}
        <div className="flex flex-wrap gap-1.5 mb-6">
          {career.keySkills.slice(0, 4).map((skill) => (
            <span
              key={skill}
              className="px-2.5 py-1 rounded-full bg-navy/[0.04] border border-navy/[0.08] text-eyebrow font-body text-navy/65 font-medium uppercase"
            >
              {skill}
            </span>
          ))}
        </div>

        {/* CTA */}
        <Button
          variant={isSelected ? 'primary' : 'secondary'}
          size="md"
          onClick={onSelect}
          className="!rounded-xl w-full"
        >
          {isSelected ? 'Viewing Roadmap' : 'View Roadmap'}
          <ChevronRight size={14} aria-hidden="true" />
        </Button>
      </div>
    </motion.div>
  )
}

export default Results
