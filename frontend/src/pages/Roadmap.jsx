import { useRef, useLayoutEffect, useState } from 'react'
import { ExternalLink, X } from 'lucide-react'
import { ROADMAPS, CAREERS } from '../data'

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

function NodeRect({ node, isHovered, isActive, onClick, onMouseEnter, onMouseLeave }) {
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
          fontSize="13" fontFamily="Inter, system-ui, sans-serif" fontWeight="500"
          pointerEvents="none"
          fill={node.type === 'required' ? 'white' : color}
          fillOpacity={node.type === 'optional' ? 0.55 : 1}>
      {node.label}
    </text>
  )

  const sharedProps = {
    onClick,
    onMouseEnter,
    onMouseLeave,
    style: { cursor: 'pointer', filter: isHovered ? glow : 'none' },
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
  const color = node ? LEVEL_COLORS[node.level] : '#22C55E'
  return (
    <div
      className="fixed right-0 top-0 h-full z-50 overflow-y-auto"
      style={{
        width: 320,
        background: '#FAF7F2',
        borderLeft: '1px solid rgba(15,27,45,0.1)',
        boxShadow: '-8px 0 32px rgba(15,27,45,0.12)',
        transform: node ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform 300ms cubic-bezier(0.4,0,0.2,1)',
        pointerEvents: node ? 'auto' : 'none',
      }}
    >
      {node && (
        <div className="p-6 pt-10">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 transition-colors"
            style={{ color: 'rgba(15,27,45,0.3)' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'rgba(15,27,45,0.8)' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'rgba(15,27,45,0.3)' }}
          >
            <X size={16} />
          </button>

          <div className="flex flex-wrap gap-2 mb-4">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded text-[11px] font-semibold"
                  style={{ background: `${color}18`, color, border: `1px solid ${color}40` }}>
              {TYPE_LABELS[node.type]}
            </span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded text-[11px] font-semibold"
                  style={{ background: `${color}10`, color, border: `1px solid ${color}25` }}>
              {LEVEL_LABELS[node.level]}
            </span>
          </div>

          <h3 className="font-display font-semibold text-lg mb-3" style={{ color: '#0F1B2D' }}>
            {node.label}
          </h3>

          <p className="font-body text-sm leading-relaxed mb-6" style={{ color: 'rgba(15,27,45,0.6)' }}>
            {node.description}
          </p>

          {node.resources?.length > 0 && (
            <div>
              <p className="font-body text-[10px] font-semibold uppercase tracking-widest mb-3"
                 style={{ color: 'rgba(15,27,45,0.35)' }}>
                Resources
              </p>
              <div className="flex flex-col gap-2">
                {node.resources.map((r) => (
                  <a key={r.url} href={r.url} target="_blank" rel="noopener noreferrer"
                     className="inline-flex items-center gap-2 text-sm font-semibold transition-opacity hover:opacity-70"
                     style={{ color: '#C9A84C' }}>
                    <ExternalLink size={13} />
                    {r.title}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Legend() {
  return (
    <div className="flex flex-col gap-2.5 p-3 rounded-lg"
         style={{ background: 'rgba(250,247,242,0.95)', border: '1px solid rgba(201,168,76,0.2)' }}>
      <p className="font-body text-[10px] font-semibold uppercase tracking-widest"
         style={{ color: 'rgba(15,27,45,0.35)' }}>
        Legend
      </p>
      <div className="flex items-center gap-2">
        <svg width={60} height={22} style={{ flexShrink: 0 }}>
          <rect x={0} y={1} width={60} height={20} rx={4} fill="#22C55E" />
        </svg>
        <span className="font-body text-xs whitespace-nowrap" style={{ color: 'rgba(15,27,45,0.65)' }}>
          Required
        </span>
      </div>
      <div className="flex items-center gap-2">
        <svg width={60} height={22} style={{ flexShrink: 0 }}>
          <rect x={0.75} y={1.75} width={58.5} height={18.5} rx={4}
                fill="none" stroke="#EAB308" strokeWidth={1.5} />
        </svg>
        <span className="font-body text-xs whitespace-nowrap" style={{ color: 'rgba(15,27,45,0.65)' }}>
          Good to Know
        </span>
      </div>
      <div className="flex items-center gap-2">
        <svg width={60} height={22} style={{ flexShrink: 0 }}>
          <rect x={0.75} y={1.75} width={58.5} height={18.5} rx={4}
                fill="none" stroke="#EF4444" strokeWidth={1.5} strokeDasharray="6,3" />
        </svg>
        <span className="font-body text-xs whitespace-nowrap" style={{ color: 'rgba(15,27,45,0.65)' }}>
          Optional
        </span>
      </div>
    </div>
  )
}

function Roadmap({ selectedCareer }) {
  const pathRefs = useRef({})
  const [drawerNode, setDrawerNode] = useState(null)
  const [hoveredNode, setHoveredNode] = useState(null)
  const [collapsed, setCollapsed] = useState({})

  const career = CAREERS.find((c) => c.id === selectedCareer)
  const roadmapData = selectedCareer ? ROADMAPS[selectedCareer] : null
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
    const raf = requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        Object.keys(refs).forEach((id, i) => {
          const path = refs[id]
          if (!path) return
          path.style.transition = `stroke-dashoffset 1.2s cubic-bezier(0.4,0,0.2,1) ${i * 0.08}s`
          path.style.strokeDashoffset = '0'
        })
      })
    })
    return () => cancelAnimationFrame(raf)
  }, [selectedCareer, roadmapData, collapsed])

  if (!selectedCareer) return null

  return (
    <>
      <section id="roadmap" className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="text-center mb-10">
            <p className="font-body text-xs font-semibold text-gold tracking-widest uppercase mb-3">
              Your Learning Roadmap
            </p>
            <h2 className="font-display font-bold text-4xl md:text-5xl text-navy mb-4">
              {career?.title} Path
            </h2>
            <p className="font-body text-navy/55 text-base max-w-lg mx-auto">
              Click any skill node to explore resources and details.
            </p>
          </div>

          {/* Toolbar: expand/collapse + legend */}
          <div className="flex items-start justify-between mb-5 flex-wrap gap-4">
            <button
              onClick={toggleAll}
              className="font-body text-xs font-semibold px-4 py-2 rounded-lg transition-colors"
              style={{
                border: '1px solid rgba(201,168,76,0.4)',
                color: '#C9A84C',
                background: 'transparent',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(201,168,76,0.08)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
            >
              {allCollapsed ? 'Expand All' : 'Collapse All'}
            </button>
            <Legend />
          </div>

          {/* SVG canvas */}
          <div style={{ overflowX: 'auto' }}>
            <svg
              width={CANVAS_W}
              height={totalH}
              style={{ display: 'block', margin: '0 auto', minWidth: CANVAS_W }}
            >
              {/* Center spine */}
              <line x1={SPINE_X} y1={0} x2={SPINE_X} y2={totalH}
                    stroke="#C9A84C" strokeWidth={1} opacity={0.2} />

              {/* Connector paths */}
              {allEdges.map((edge) => (
                <path
                  key={edge.id}
                  ref={(el) => { pathRefs.current[edge.id] = el }}
                  d={edge.d}
                  stroke="#C9A84C" strokeWidth={2} fill="none" opacity={0.8}
                />
              ))}

              {/* Sections */}
              {layoutSections.map((section) => {
                const isCollapsed = !!collapsed[section.id]
                return (
                  <g key={section.id}>
                    {/* Section header — clickable to collapse */}
                    <g onClick={() => toggleSection(section.id)} style={{ cursor: 'pointer' }}>
                      <rect
                        x={SPINE_X - SECTION_HEADER_W / 2} y={section.y}
                        width={SECTION_HEADER_W} height={SECTION_HEADER_H} rx={6}
                        fill="rgba(15,27,45,0.07)" stroke="rgba(15,27,45,0.12)" strokeWidth={1}
                      />
                      <text
                        x={SPINE_X - 10} y={section.y + SECTION_HEADER_H / 2}
                        textAnchor="middle" dominantBaseline="middle"
                        fontSize="13" fontFamily="Inter, system-ui, sans-serif" fontWeight="600"
                        fill="#0F1B2D" pointerEvents="none"
                      >
                        {section.label}
                      </text>
                      <text
                        x={SPINE_X + SECTION_HEADER_W / 2 - 16}
                        y={section.y + SECTION_HEADER_H / 2}
                        textAnchor="middle" dominantBaseline="middle"
                        fontSize="11" fill="rgba(15,27,45,0.4)" pointerEvents="none"
                      >
                        {isCollapsed ? '▸' : '▾'}
                      </text>
                    </g>

                    {/* Child nodes */}
                    {!isCollapsed && section.nodes.map((node) => (
                      <NodeRect
                        key={node.id}
                        node={node}
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
        </div>
      </section>

      <NodeDrawer node={drawerNode} onClose={() => setDrawerNode(null)} />
    </>
  )
}

export default Roadmap
