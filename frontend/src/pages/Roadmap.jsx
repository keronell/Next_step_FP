import { useRef, useLayoutEffect, useEffect, useState } from 'react'
import { ExternalLink, X } from 'lucide-react'
import { ROADMAPS, CAREERS } from '../data'
import { useReveal } from '../hooks/useReveal'

const LEVEL_COLORS = {
  beginner:     { fill: '#22C55E', text: '#fff', label: 'Beginner' },
  intermediate: { fill: '#EAB308', text: '#0F1B2D', label: 'Intermediate' },
  advanced:     { fill: '#EF4444', text: '#fff', label: 'Advanced' },
}

const VIEWBOX_W = 800
const VIEWBOX_H = 560

function cubicBez(from, to) {
  const cy = (from.y + to.y) / 2
  return `M ${from.x} ${from.y + 18} C ${from.x} ${cy}, ${to.x} ${cy}, ${to.x} ${to.y - 18}`
}

function Roadmap({ selectedCareer, activeTooltip, setActiveTooltip }) {
  const revealRef = useReveal(0.08)
  const svgRef = useRef(null)
  const containerRef = useRef(null)
  const pathRefs = useRef({})
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 })

  const career = CAREERS.find((c) => c.id === selectedCareer)
  const roadmapData = selectedCareer ? ROADMAPS[selectedCareer] : null
  const nodes = roadmapData?.nodes ?? []

  // Build edge list from parentId references
  const edges = nodes
    .filter((n) => n.parentId !== null)
    .map((n) => {
      const parent = nodes.find((p) => p.id === n.parentId)
      return parent ? { id: `${parent.id}-${n.id}`, from: parent, to: n } : null
    })
    .filter(Boolean)

  // Set up dasharray and animate dashoffset → 0 via JS (avoids CSS px/user-unit mismatch)
  useLayoutEffect(() => {
    if (!roadmapData) return
    const refs = pathRefs.current
    // Reset: stop transition, set initial state
    Object.keys(refs).forEach((id) => {
      const path = refs[id]
      if (!path) return
      const len = path.getTotalLength()
      path.style.transition = 'none'
      path.style.strokeDasharray = `${len}`
      path.style.strokeDashoffset = `${len}`
    })
    // After a frame, enable transition and animate to 0
    const raf = requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        Object.keys(refs).forEach((id, i) => {
          const path = refs[id]
          if (!path) return
          path.style.transition = `stroke-dashoffset 1.4s cubic-bezier(0.4,0,0.2,1) ${i * 0.1}s`
          path.style.strokeDashoffset = '0'
        })
      })
    })
    return () => cancelAnimationFrame(raf)
  }, [selectedCareer, roadmapData])

  const handleNodeClick = (node, e) => {
    if (activeTooltip === node.id) {
      setActiveTooltip(null)
      return
    }
    // Calculate tooltip position relative to container
    const container = containerRef.current
    const svg = svgRef.current
    if (!container || !svg) return
    const cRect = container.getBoundingClientRect()
    const sRect = svg.getBoundingClientRect()
    const scaleX = sRect.width / VIEWBOX_W
    const scaleY = sRect.height / VIEWBOX_H
    const svgOffsetX = sRect.left - cRect.left
    const svgOffsetY = sRect.top - cRect.top
    const tx = svgOffsetX + node.x * scaleX
    const ty = svgOffsetY + node.y * scaleY
    setTooltipPos({ x: tx, y: ty })
    setActiveTooltip(node.id)
  }

  const activeNode = nodes.find((n) => n.id === activeTooltip)

  if (!selectedCareer) return null

  return (
    <section id="roadmap" className="py-24 px-6">
      <div className="max-w-6xl mx-auto">
        <div ref={revealRef} className="reveal text-center mb-12">
          <p className="font-body text-xs font-semibold text-gold tracking-widest uppercase mb-3">
            Your Learning Roadmap
          </p>
          <h2 className="font-display font-bold text-4xl md:text-5xl text-navy mb-4">
            {career?.title} Path
          </h2>
          <p className="font-body text-navy/55 text-base max-w-lg mx-auto mb-6">
            Click any skill node to see a description and a resource link.
          </p>

          {/* Legend */}
          <div className="flex justify-center gap-4 flex-wrap">
            {Object.entries(LEVEL_COLORS).map(([level, { fill, label }]) => (
              <div key={level} className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full" style={{ background: fill }} />
                <span className="font-body text-xs text-navy/50">{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* SVG Tree */}
        <div ref={containerRef} className="relative">
          <svg
            ref={svgRef}
            viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
            className="w-full max-w-3xl mx-auto block"
            preserveAspectRatio="xMidYMid meet"
            style={{ overflow: 'visible' }}
          >
            {/* Edges */}
            {edges.map((edge) => (
              <path
                key={edge.id}
                ref={(el) => { pathRefs.current[edge.id] = el }}
                d={cubicBez(edge.from, edge.to)}
                className="path-draw"
                stroke="#C9A84C"
                strokeWidth="2"
                fill="none"
                strokeLinecap="round"
                opacity="0.5"
              />
            ))}

            {/* Nodes */}
            {nodes.map((node) => {
              const colors = LEVEL_COLORS[node.level]
              const isActive = activeTooltip === node.id
              return (
                <g
                  key={node.id}
                  onClick={(e) => handleNodeClick(node, e)}
                  style={{ cursor: 'pointer' }}
                >
                  {/* Glow ring on active */}
                  {isActive && (
                    <rect
                      x={node.x - 62}
                      y={node.y - 22}
                      width={124}
                      height={44}
                      rx={22}
                      fill="none"
                      stroke={colors.fill}
                      strokeWidth={3}
                      opacity={0.35}
                    />
                  )}
                  {/* Pill background */}
                  <rect
                    x={node.x - 56}
                    y={node.y - 18}
                    width={112}
                    height={36}
                    rx={18}
                    fill={colors.fill}
                    opacity={isActive ? 1 : 0.9}
                    className="transition-opacity duration-150 hover:opacity-100"
                  />
                  {/* Label */}
                  <text
                    x={node.x}
                    y={node.y + 5}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill={colors.text}
                    fontSize="12"
                    fontFamily="Inter, system-ui, sans-serif"
                    fontWeight="500"
                    pointerEvents="none"
                  >
                    {node.label}
                  </text>
                  {/* Click indicator chevron */}
                  <text
                    x={node.x + 44}
                    y={node.y + 5}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill={colors.text}
                    fontSize="9"
                    opacity="0.7"
                    pointerEvents="none"
                  >
                    ▾
                  </text>
                </g>
              )
            })}
          </svg>

          {/* Tooltip */}
          {activeNode && (
            <NodeTooltip
              node={activeNode}
              pos={tooltipPos}
              onClose={() => setActiveTooltip(null)}
            />
          )}
        </div>
      </div>
    </section>
  )
}

function NodeTooltip({ node, pos, onClose }) {
  const colors = LEVEL_COLORS[node.level]

  return (
    <div
      className="absolute z-50 w-72 bg-white rounded-2xl shadow-xl border border-navy/10 p-5"
      style={{
        left: Math.min(pos.x - 144, window.innerWidth - 310),
        top: pos.y + 28,
        transform: 'translateX(0)',
      }}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-3 right-3 text-navy/30 hover:text-navy transition-colors"
      >
        <X size={14} />
      </button>

      {/* Level badge */}
      <div
        className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-body font-semibold mb-3"
        style={{ background: `${colors.fill}20`, color: colors.fill, border: `1px solid ${colors.fill}40` }}
      >
        {colors.label}
      </div>

      <h4 className="font-display font-semibold text-base text-navy mb-2">{node.label}</h4>
      <p className="font-body text-xs text-navy/60 leading-relaxed mb-4">{node.description}</p>

      {node.resource && (
        <a
          href={node.resource.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs font-body font-semibold text-gold hover:text-gold/80 transition-colors"
        >
          <ExternalLink size={12} />
          {node.resource.title}
        </a>
      )}
    </div>
  )
}

export default Roadmap
