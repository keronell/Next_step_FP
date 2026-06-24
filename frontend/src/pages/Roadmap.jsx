import { useRef, useLayoutEffect, useEffect, useState } from 'react'
import { ExternalLink, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { ROADMAPS, CAREERS } from '../data'
import { fetchRoadmap } from '../api'
import SectionHeading from '../components/ui/SectionHeading.jsx'

const CANVAS_W = 1400
const SPINE_X = 700
const NODE_H = 40
const NODE_MIN_W = 140
const NODE_CHAR_W = 8
const NODE_PAD_X = 24
const SECTION_HEADER_H = 44
const SECTION_HEADER_W = 240
const TOP_PAD = 80
const HEADER_TO_ROW_GAP = 60
const ROW_TO_HEADER_GAP = 80
const NODE_COL_GAP = 40

const FONT = { node: 13, section: 13, legendLabel: 11, badge: 11 }

const LEVEL_COLORS = {
  beginner:     '#22C55E',
  intermediate: '#EAB308',
  advanced:     '#EF4444',
}

const LEVEL_LABELS = {
  beginner:     'Beginner',
  intermediate: 'Intermediate',
  advanced:     'Advanced',
}

const TYPE_LABELS = {
  'required':     'Required',
  'good-to-know': 'Good to Know',
  'optional':     'Optional',
}

function calcNodeWidth(label) {
  return Math.max(NODE_MIN_W, label.length * NODE_CHAR_W + NODE_PAD_X * 2)
}

function computeLayout(sections, collapsed) {
  let currentY = TOP_PAD
  const layoutSections = []

  for (const section of sections) {
    const sectionY = currentY
    const childrenY = sectionY + SECTION_HEADER_H + HEADER_TO_ROW_GAP

    const nodesWithWidths = section.nodes.map((n) => ({
      ...n,
      width: calcNodeWidth(n.label),
    }))

    const totalRowW =
      nodesWithWidths.reduce((sum, n) => sum + n.width, 0) +
      Math.max(0, nodesWithWidths.length - 1) * NODE_COL_GAP

    let startX = SPINE_X - totalRowW / 2
    const positionedNodes = nodesWithWidths.map((n) => {
      const x = startX + n.width / 2
      startX += n.width + NODE_COL_GAP
      return { ...n, x, y: childrenY }
    })

    layoutSections.push({ ...section, y: sectionY, childrenY, nodes: positionedNodes })

    currentY = collapsed[section.id]
      ? sectionY + SECTION_HEADER_H + ROW_TO_HEADER_GAP
      : childrenY + NODE_H / 2 + ROW_TO_HEADER_GAP
  }

  return { layoutSections, totalH: currentY + 40 }
}

function elbowPath(fromX, fromY, toX, toY) {
  const midY = fromY + (toY - fromY) / 2
  return `M ${fromX} ${fromY} L ${fromX} ${midY} L ${toX} ${midY} L ${toX} ${toY}`
}

// Inline Lucide-style chevron paths (size 14, centered at 0,0)
function ChevronSVG({ cx, cy, open, color = 'rgba(15,27,45,0.55)' }) {
  // Lucide chevron-right path: M9 18l6-6-6-6 (in 24x24 viewport)
  // Lucide chevron-down path:  M6 9l6 6 6-6
  // We draw with stroke at scale 0.6 (~14px equivalent) around (cx, cy)
  const s = 0.6
  const tx = cx - 12 * s
  const ty = cy - 12 * s
  const d = open ? 'M6 9l6 6 6-6' : 'M9 18l6-6-6-6'
  return (
    <g transform={`translate(${tx} ${ty}) scale(${s})`} pointerEvents="none">
      <path d={d} stroke={color} strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </g>
  )
}

function NodeRect({ node, isHovered, isActive, isRevealed, onClick, onMouseEnter, onMouseLeave }) {
  const color = LEVEL_COLORS[node.level]
  const w = node.width
  const rx = node.x - w / 2
  const ry = node.y - NODE_H / 2
  const glow = `drop-shadow(0 0 7px ${color}90)`

  const activeRing = isActive && (
    <rect x={rx - 3} y={ry - 3} width={w + 6} height={NODE_H + 6} rx={8}
          fill="none" stroke={color} strokeWidth={2} opacity={0.35} />
  )

  const label = (
    <text x={node.x} y={node.y} textAnchor="middle" dominantBaseline="middle"
          fontSize={FONT.node} fontFamily="Inter, system-ui, sans-serif" fontWeight="500"
          pointerEvents="none"
          fill={node.type === 'required' ? 'white' : color}
          fillOpacity={node.type === 'optional' ? 0.55 : 1}>
      {node.label}
    </text>
  )

  const revealStyle = {
    opacity: isRevealed ? 1 : 0,
    transform: isRevealed ? 'translateY(0px)' : 'translateY(8px)',
    transition: 'opacity 0.5s var(--ease-standard), transform 0.5s var(--ease-standard)',
  }

  const sharedProps = {
    onClick,
    onMouseEnter,
    onMouseLeave,
    style: { cursor: 'pointer', filter: isHovered ? glow : 'none', ...revealStyle },
  }

  if (node.type === 'required') {
    return (
      <g {...sharedProps}>
        {activeRing}
        <rect x={rx} y={ry} width={w} height={NODE_H} rx={6} fill={color} />
        {label}
      </g>
    )
  }

  if (node.type === 'good-to-know') {
    return (
      <g {...sharedProps}>
        {activeRing}
        <rect x={rx} y={ry} width={w} height={NODE_H} rx={6}
              fill="none" stroke={color} strokeWidth={1.5} />
        {label}
      </g>
    )
  }

  return (
    <g {...sharedProps}>
      {activeRing}
      <rect x={rx} y={ry} width={w} height={NODE_H} rx={6}
            fill="none" stroke={color} strokeWidth={1.5} strokeDasharray="6,3" />
      {label}
    </g>
  )
}

function NodeDrawer({ node, onClose }) {
  const color = node ? LEVEL_COLORS[node.level] : 'var(--color-gold)'

  return (
    <AnimatePresence>
      {node && (
        <>
          {/* Backdrop scrim */}
          <motion.div
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.24 }}
            className="fixed inset-0 z-40 backdrop-blur-[2px] bg-navy/30"
          />

          {/* Drawer panel */}
          <motion.div
            role="dialog"
            aria-modal="true"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 280, damping: 32 }}
            className="fixed right-0 top-0 h-full z-50 overflow-y-auto bg-cream border-l border-navy/[0.1] shadow-[-8px_0_32px_rgba(15,27,45,0.12)]"
            style={{ width: 340 }}
          >
          <div className="p-6 pt-10">
            <button
              onClick={onClose}
              aria-label="Close drawer"
              className="focus-ring absolute top-4 right-4 inline-flex items-center justify-center w-8 h-8 rounded-full text-navy/40 hover:text-navy hover:bg-navy/[0.06] transition-colors duration-fast"
            >
              <X size={16} aria-hidden="true" />
            </button>

            <div className="flex flex-wrap gap-2 mb-4">
              <span
                className="inline-flex items-center px-2.5 py-0.5 rounded text-eyebrow font-semibold uppercase"
                style={{ background: `${color}1F`, color, border: `1px solid ${color}40` }}
              >
                {TYPE_LABELS[node.type]}
              </span>
              <span
                className="inline-flex items-center px-2.5 py-0.5 rounded text-eyebrow font-semibold uppercase"
                style={{ background: `${color}14`, color, border: `1px solid ${color}25` }}
              >
                {LEVEL_LABELS[node.level]}
              </span>
            </div>

            <h3 className="font-display font-semibold text-h3 text-navy mb-3 tracking-tight">
              {node.label}
            </h3>

            <p className="font-body text-small text-navy/65 leading-relaxed mb-6">
              {node.description}
            </p>

            {node.resources?.length > 0 && (
              <div>
                <p className="font-body text-eyebrow font-semibold uppercase text-navy/45 mb-3">
                  Resources
                </p>
                <div className="flex flex-col gap-2">
                  {node.resources.map((r) => (
                    <a
                      key={r.url}
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="focus-ring inline-flex items-center gap-2 text-small font-semibold text-gold hover:opacity-70 transition-opacity duration-fast"
                    >
                      <ExternalLink size={13} aria-hidden="true" />
                      {r.title}
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

function Legend() {
  return (
    <div className="flex flex-col gap-2.5 p-3 rounded-lg bg-cream/95 backdrop-blur-sm border border-gold/25 shadow-sm">
      <p className="font-body text-eyebrow font-semibold uppercase text-navy/45">
        Legend
      </p>
      <div className="flex items-center gap-2">
        <svg width={60} height={22} style={{ flexShrink: 0 }}>
          <rect x={0} y={1} width={60} height={20} rx={4} fill="#22C55E" />
        </svg>
        <span className="font-body text-small text-navy/70 whitespace-nowrap">Required</span>
      </div>
      <div className="flex items-center gap-2">
        <svg width={60} height={22} style={{ flexShrink: 0 }}>
          <rect x={0.75} y={1.75} width={58.5} height={18.5} rx={4}
                fill="none" stroke="#EAB308" strokeWidth={1.5} />
        </svg>
        <span className="font-body text-small text-navy/70 whitespace-nowrap">Good to Know</span>
      </div>
      <div className="flex items-center gap-2">
        <svg width={60} height={22} style={{ flexShrink: 0 }}>
          <rect x={0.75} y={1.75} width={58.5} height={18.5} rx={4}
                fill="none" stroke="#EF4444" strokeWidth={1.5} strokeDasharray="6,3" />
        </svg>
        <span className="font-body text-small text-navy/70 whitespace-nowrap">Optional</span>
      </div>
    </div>
  )
}

function Roadmap({ selectedCareer, missingSkills = [] }) {
  const pathRefs = useRef({})
  const revealTimersRef = useRef([])
  const [drawerNode, setDrawerNode] = useState(null)
  const [hoveredNode, setHoveredNode] = useState(null)
  const [hoveredSection, setHoveredSection] = useState(null)
  const [collapsed, setCollapsed] = useState({})
  const [revealedNodes, setRevealedNodes] = useState(new Set())
  const [roadmapData, setRoadmapData] = useState(null)

  const career = CAREERS.find((c) => c.id === selectedCareer)

  // Fetch the roadmap from the backend; fall back to the bundled ROADMAPS if it's
  // down (same offline-estimate spirit as the questionnaire results).
  useEffect(() => {
    if (!selectedCareer) {
      setRoadmapData(null)
      return
    }
    let cancelled = false
    fetchRoadmap(selectedCareer, missingSkills)
      .then((data) => { if (!cancelled) setRoadmapData(data) })
      .catch(() => { if (!cancelled) setRoadmapData(ROADMAPS[selectedCareer] ?? null) })
    return () => { cancelled = true }
  }, [selectedCareer]) // eslint-disable-line react-hooks/exhaustive-deps

  const sections = roadmapData?.sections ?? []

  const { layoutSections, totalH } = computeLayout(sections, collapsed)

  const allCollapsed = sections.length > 0 && sections.every((s) => !!collapsed[s.id])

  const toggleAll = () => {
    if (allCollapsed) {
      setCollapsed({})
    } else {
      const next = {}
      sections.forEach((s) => { next[s.id] = true })
      setCollapsed(next)
    }
  }

  const toggleSection = (id) => setCollapsed((prev) => ({ ...prev, [id]: !prev[id] }))

  const handleNodeClick = (node) => {
    setDrawerNode((prev) => (prev?.id === node.id ? null : node))
  }

  // Collect visible edge descriptors for animation
  const allEdges = []
  layoutSections.forEach((section) => {
    if (!collapsed[section.id]) {
      section.nodes.forEach((node) => {
        allEdges.push({
          id: `${section.id}--${node.id}`,
          d: elbowPath(
            SPINE_X, section.y + SECTION_HEADER_H,
            node.x, node.y - NODE_H / 2,
          ),
        })
      })
    }
  })

  useEffect(() => {
    setRevealedNodes(new Set())
  }, [selectedCareer, collapsed])

  useLayoutEffect(() => {
    if (!roadmapData) return
    const refs = pathRefs.current
    Object.keys(refs).forEach((id) => {
      const path = refs[id]
      if (!path) return
      const len = path.getTotalLength()
      path.style.transition = 'none'
      path.style.strokeDasharray = `${len}`
      path.style.strokeDashoffset = `${len}`
    })

    revealTimersRef.current.forEach(clearTimeout)
    revealTimersRef.current = []

    const raf = requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        Object.keys(refs).forEach((id, i) => {
          const path = refs[id]
          if (!path) return
          path.style.transition = `stroke-dashoffset 1.2s cubic-bezier(0.4,0,0.2,1) ${i * 0.08}s`
          path.style.strokeDashoffset = '0'

          const nodeId = id.split('--')[1]
          const t = setTimeout(() => {
            setRevealedNodes(prev => new Set([...prev, nodeId]))
          }, i * 80 + 1400)
          revealTimersRef.current.push(t)
        })
      })
    })

    return () => {
      cancelAnimationFrame(raf)
      revealTimersRef.current.forEach(clearTimeout)
    }
  }, [selectedCareer, roadmapData, collapsed])

  if (!selectedCareer) return null

  return (
    <>
      <section id="roadmap" className="py-24 px-6 relative">
        <div className="max-w-7xl mx-auto relative">
          {/* Header */}
          <div className="mb-10">
            <SectionHeading
              eyebrow="Your Learning Roadmap"
              title={`${career?.title} Path`}
              lede="Click any skill node to explore resources and details."
              align="center"
            />
          </div>

          {/* Toolbar */}
          <div className="flex items-center justify-start mb-5">
            <button
              onClick={toggleAll}
              className="focus-ring font-body text-eyebrow font-semibold uppercase px-4 py-2 rounded-lg border border-gold/40 text-gold hover:bg-gold/[0.08] transition-colors duration-fast"
            >
              {allCollapsed ? 'Expand All' : 'Collapse All'}
            </button>
          </div>

          {/* SVG canvas + sticky legend wrapper */}
          <div className="relative">
            <div style={{ overflowX: 'auto' }}>
              <svg
                width={CANVAS_W}
                height={totalH}
                style={{ display: 'block', margin: '0 auto', minWidth: CANVAS_W }}
              >
                {/* Center spine */}
                <line x1={SPINE_X} y1={0} x2={SPINE_X} y2={totalH}
                      stroke="var(--color-gold)" strokeWidth={1} opacity={0.2} />

                {/* Connector paths */}
                {allEdges.map((edge) => (
                  <path
                    key={edge.id}
                    ref={(el) => { pathRefs.current[edge.id] = el }}
                    d={edge.d}
                    stroke="var(--color-gold)" strokeWidth={2} fill="none" opacity={0.8}
                  />
                ))}

                {/* Sections */}
                {layoutSections.map((section) => {
                  const isCollapsed = !!collapsed[section.id]
                  const isHovered = hoveredSection === section.id
                  return (
                    <g key={section.id}>
                      {/* Section header — clickable to collapse */}
                      <g
                        onClick={() => toggleSection(section.id)}
                        onMouseEnter={() => setHoveredSection(section.id)}
                        onMouseLeave={() => setHoveredSection(null)}
                        style={{ cursor: 'pointer' }}
                      >
                        <rect
                          x={SPINE_X - SECTION_HEADER_W / 2} y={section.y}
                          width={SECTION_HEADER_W} height={SECTION_HEADER_H} rx={6}
                          fill={isHovered ? 'rgba(15,27,45,0.10)' : 'rgba(15,27,45,0.06)'}
                          stroke={isHovered ? 'rgba(201,168,76,0.45)' : 'rgba(15,27,45,0.12)'}
                          strokeWidth={1}
                          style={{ transition: 'fill var(--motion-fast), stroke var(--motion-fast)' }}
                        />
                        <text
                          x={SPINE_X - 10} y={section.y + SECTION_HEADER_H / 2}
                          textAnchor="middle" dominantBaseline="middle"
                          fontSize={FONT.section} fontFamily="Inter, system-ui, sans-serif" fontWeight="600"
                          fill="var(--color-navy)" pointerEvents="none"
                        >
                          {section.label}
                        </text>
                        <ChevronSVG
                          cx={SPINE_X + SECTION_HEADER_W / 2 - 18}
                          cy={section.y + SECTION_HEADER_H / 2}
                          open={!isCollapsed}
                        />
                      </g>

                      {/* Child nodes */}
                      {!isCollapsed && section.nodes.map((node) => (
                        <NodeRect
                          key={node.id}
                          node={node}
                          isRevealed={revealedNodes.has(node.id)}
                          isHovered={hoveredNode === node.id}
                          isActive={drawerNode?.id === node.id}
                          onClick={() => handleNodeClick(node)}
                          onMouseEnter={() => setHoveredNode(node.id)}
                          onMouseLeave={() => setHoveredNode(null)}
                        />
                      ))}
                    </g>
                  )
                })}
              </svg>
            </div>

            {/* Sticky legend — top-right of the canvas wrapper, stays put during horizontal scroll */}
            <div className="absolute top-2 right-2 pointer-events-auto z-10">
              <Legend />
            </div>
          </div>
        </div>
      </section>

      <NodeDrawer node={drawerNode} onClose={() => setDrawerNode(null)} />
    </>
  )
}

export default Roadmap
