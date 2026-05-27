import { useEffect, useState } from 'react'
import { Monitor, Server, BarChart2, Layers, Compass, Pen, ChevronRight, Trophy, Medal, Award } from 'lucide-react'
import { useReveal } from '../hooks/useReveal'

const ICON_MAP = {
  Monitor, Server, BarChart2, Layers, Compass, Pen,
}

const RANK_STYLES = [
  { icon: Trophy, label: 'Best Match', color: '#C9A84C', bg: '#C9A84C15', border: '#C9A84C40' },
  { icon: Medal, label: 'Strong Match', color: '#6B7280', bg: '#6B728010', border: '#6B728030' },
  { icon: Award, label: 'Great Fit', color: '#92400E', bg: '#92400E10', border: '#92400E30' },
]

function Results({ phase, results, onSelectCareer, selectedCareer }) {
  const revealRef = useReveal(0.1)

  if (phase !== 'results_ready' || !results) return null

  return (
    <section id="results" className="py-24 px-6 bg-navy/[0.02]">
      <div className="max-w-6xl mx-auto">
        <div ref={revealRef} className="reveal text-center mb-14">
          <p className="font-body text-xs font-semibold text-gold tracking-widest uppercase mb-3">
            Your Results
          </p>
          <h2 className="font-display font-bold text-4xl md:text-5xl text-navy mb-4">
            Your top career matches
          </h2>
          <p className="font-body text-navy/55 text-lg max-w-md mx-auto">
            Based on your answers, here are the tech roles where you're most likely to thrive.
          </p>
        </div>

        <CardsRow results={results} onSelectCareer={onSelectCareer} selectedCareer={selectedCareer} />
      </div>
    </section>
  )
}

function CardsRow({ results, onSelectCareer, selectedCareer }) {
  const rowRef = useReveal(0.05)

  return (
    <div ref={rowRef} className="reveal-stagger reveal grid grid-cols-1 md:grid-cols-3 gap-6">
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
  )
}

function CareerCard({ career, rank, isSelected, onSelect }) {
  const [displayPercent, setDisplayPercent] = useState(0)
  const rankStyle = RANK_STYLES[rank]
  const RankIcon = rankStyle.icon
  const CareerIcon = ICON_MAP[career.icon] || Monitor

  useEffect(() => {
    const start = Date.now()
    const duration = 1000
    const target = career.matchPercent
    const tick = () => {
      const elapsed = Date.now() - start
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplayPercent(Math.round(eased * target))
      if (progress < 1) requestAnimationFrame(tick)
    }
    const raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [career.matchPercent])

  return (
    <div
      className={`card-hover relative flex flex-col rounded-2xl border overflow-hidden bg-white transition-all duration-200
        ${isSelected
          ? 'border-gold shadow-lg shadow-gold/15 ring-2 ring-gold/30'
          : 'border-navy/8 shadow-sm hover:border-gold/40'
        }`}
    >
      {/* Gold top accent bar */}
      <div
        className="h-1 w-full"
        style={{ background: `linear-gradient(to right, ${rankStyle.color}80, ${rankStyle.color})` }}
      />

      <div className="p-6 flex flex-col flex-1">
        {/* Rank badge */}
        <div
          className="self-start flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-body font-semibold mb-4"
          style={{ background: rankStyle.bg, border: `1px solid ${rankStyle.border}`, color: rankStyle.color }}
        >
          <RankIcon size={11} />
          {rankStyle.label}
        </div>

        {/* Match % + icon */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: rankStyle.bg, border: `1px solid ${rankStyle.border}` }}
            >
              <CareerIcon size={18} style={{ color: rankStyle.color }} />
            </div>
          </div>
          <div className="text-right">
            <span className="font-display font-bold text-4xl text-navy tabular-nums">
              {displayPercent}
            </span>
            <span className="font-body text-lg text-gold font-semibold">%</span>
          </div>
        </div>

        {/* Title */}
        <h3 className="font-display font-semibold text-xl text-navy mb-2">
          {career.title}
        </h3>

        {/* Description */}
        <p className="font-body text-sm text-navy/55 leading-relaxed mb-5 flex-1">
          {career.description}
        </p>

        {/* Key skills */}
        <div className="flex flex-wrap gap-1.5 mb-6">
          {career.keySkills.slice(0, 4).map((skill) => (
            <span
              key={skill}
              className="px-2.5 py-1 rounded-full bg-navy/5 border border-navy/8 text-xs font-body text-navy/60 font-medium"
            >
              {skill}
            </span>
          ))}
        </div>

        {/* CTA */}
        <button
          onClick={onSelect}
          className={`w-full py-3 rounded-xl text-sm font-body font-semibold flex items-center justify-center gap-1.5 transition-all duration-150
            ${isSelected
              ? 'bg-gold text-navy shadow-sm'
              : 'bg-navy/5 text-navy hover:bg-gold hover:text-navy border border-navy/10 hover:border-gold'
            }`}
        >
          {isSelected ? 'Viewing Roadmap' : 'View Roadmap'}
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  )
}

export default Results
