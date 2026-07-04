import { Fragment, useRef, useEffect, useState } from 'react'
import { ExternalLink, X, Check, ChevronDown, ChevronRight } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { ROADMAPS, CAREERS } from '../data'
import { fetchRoadmap, fetchRoadmapProgress, saveRoadmapProgress } from '../api'
import { useAuth } from '../contexts/AuthContext'
import SectionHeading from '../components/ui/SectionHeading.jsx'

const progressKey = (careerId) => `nextstep_roadmap_progress_${careerId}`

// DEV-46: node color = the user's status on that skill, one meaning per color.
const STATUS_COLORS = {
  mastered: '#22C55E', // green  — mastered / completed skill
  next:     '#F97316', // orange — in progress / recommended next
  gap:      '#EF4444', // red    — not started / skill gap
}

const STATUS_LABELS = {
  mastered: 'Mastered / completed',
  next:     'Recommended next',
  gap:      'Skill gap / not started',
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

// Skill ↔ node-label matching: substring first, then canonical-token subset,
// so "SQL" colors the "Databases" node and "Data Viz" hits "Data Visualization".
// Aliases map synonym tokens to one canonical id (values are the singular form).
const TOKEN_ALIASES = {
  sql: 'database',
  postgresql: 'database',
  mysql: 'database',
  mongodb: 'database',
  js: 'javascript',
  ts: 'typescript',
  api: 'rest',
  viz: 'visualization',
  auth: 'security',
  authentication: 'security',
  user: 'ux',
}

const singular = (t) => (t.length > 3 && t.endsWith('s') && !t.endsWith('ss') ? t.slice(0, -1) : t)
const canonToken = (t) => TOKEN_ALIASES[t] ?? TOKEN_ALIASES[singular(t)] ?? singular(t)
const tokenize = (s) =>
  new Set(s.toLowerCase().split(/[^a-z0-9+#]+/).filter(Boolean).map(canonToken))
const isSubset = (a, b) => [...a].every((t) => b.has(t))

const skillHits = (skills, label) => {
  const l = label.toLowerCase()
  const lt = tokenize(label)
  return skills.some((s) => {
    const t = String(s).toLowerCase()
    if (l.includes(t) || t.includes(l)) return true
    const st = tokenize(t)
    return st.size > 0 && (isSubset(st, lt) || isSubset(lt, st))
  })
}

function nodeStatus(node, completedNodes, matchedSkills, missingSkills) {
  if (completedNodes.has(node.id) || skillHits(matchedSkills, node.label)) return 'mastered'
  if (skillHits(missingSkills, node.label)) return 'gap'
  return 'next'
}

// Type keeps its shape language (solid / outline / dashed); color now carries status.
function nodeTypeStyle(type, color) {
  if (type === 'required') return { background: color, color: 'white' }
  if (type === 'good-to-know') return { border: `1.5px solid ${color}`, color }
  return { border: `1.5px dashed ${color}`, color, opacity: 0.7 }
}

function NodeButton({ node, status, isCompleted, isActive, delay, onClick }) {
  const color = STATUS_COLORS[status]
  const shadows = []
  // Completed decor (gold ring + check badge) stays a separate system from the
  // status color: it marks "you ticked this off", not what the assessment says.
  if (isCompleted) shadows.push('0 0 0 2px var(--color-cream), 0 0 0 4px var(--color-gold)')
  if (isActive) shadows.push(`0 0 12px ${color}80`)

  return (
    <motion.button
      onClick={onClick}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      whileHover={{ scale: 1.04 }}
      className="focus-ring relative rounded-md px-5 py-2.5 font-body text-[13px] font-medium text-center cursor-pointer"
      style={{ ...nodeTypeStyle(node.type, color), boxShadow: shadows.join(', ') || undefined }}
    >
      {node.label}
      {isCompleted && (
        <span
          aria-label="Marked complete"
          className="absolute -top-2 -right-2 w-[18px] h-[18px] rounded-full bg-gold border border-cream flex items-center justify-center"
        >
          <Check size={11} strokeWidth={3} className="text-cream" aria-hidden="true" />
        </span>
      )}
    </motion.button>
  )
}

function NodeDrawer({ node, status, onClose, isCompleted, onToggleComplete }) {
  const color = node ? STATUS_COLORS[status] : 'var(--color-gold)'

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
                {STATUS_LABELS[status]}
              </span>
              <span
                className="inline-flex items-center px-2.5 py-0.5 rounded text-eyebrow font-semibold uppercase"
                style={{ background: `${color}14`, color, border: `1px solid ${color}25` }}
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

            <button
              onClick={onToggleComplete}
              className={`focus-ring w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 mb-6 rounded-xl font-body text-small font-semibold transition-colors duration-fast border ${
                isCompleted
                  ? 'bg-gold text-cream border-gold hover:bg-gold/90'
                  : 'bg-transparent text-gold border-gold/50 hover:bg-gold/[0.08]'
              }`}
            >
              <Check size={15} aria-hidden="true" />
              {isCompleted ? 'Completed' : 'Mark as complete'}
            </button>

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
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2.5 rounded-lg bg-cream/95 border border-gold/25 shadow-sm">
      <p className="font-body text-eyebrow font-semibold uppercase text-navy/45">
        Legend
      </p>
      {Object.keys(STATUS_COLORS).map((status) => (
        <div key={status} className="flex items-center gap-2">
          <span
            className="w-[26px] h-[14px] rounded shrink-0"
            style={{ background: STATUS_COLORS[status] }}
          />
          <span className="font-body text-small text-navy/70 whitespace-nowrap">
            {STATUS_LABELS[status]}
          </span>
        </div>
      ))}
      <div className="flex items-center gap-2 pl-5 border-l border-navy/[0.08]">
        <span className="relative w-[26px] h-[14px] rounded shrink-0 bg-navy/[0.08] shadow-[0_0_0_1.5px_var(--color-cream),0_0_0_3px_var(--color-gold)]">
          <span className="absolute -top-1.5 -right-1.5 w-[12px] h-[12px] rounded-full bg-gold border border-cream flex items-center justify-center">
            <Check size={8} strokeWidth={3.5} className="text-cream" aria-hidden="true" />
          </span>
        </span>
        <span className="font-body text-small text-navy/70 whitespace-nowrap">
          Marked complete by you
        </span>
      </div>
    </div>
  )
}

function Roadmap({ selectedCareer, missingSkills = [], matchedSkills = [] }) {
  const saveSeqRef = useRef(0)  // monotonic id so only the latest save reconciliation wins
  const [drawerNode, setDrawerNode] = useState(null)
  const [collapsed, setCollapsed] = useState({})
  const [roadmapData, setRoadmapData] = useState(null)
  const [completedNodes, setCompletedNodes] = useState(new Set())

  const { user } = useAuth()
  const career = CAREERS.find((c) => c.id === selectedCareer)

  // Load completed nodes for this career: from Supabase when logged in, else localStorage.
  useEffect(() => {
    if (!selectedCareer) { setCompletedNodes(new Set()); return }
    let cancelled = false
    if (user) {
      fetchRoadmapProgress(selectedCareer)
        .then((d) => { if (!cancelled) setCompletedNodes(new Set(d.completed_nodes || [])) })
        .catch(() => { if (!cancelled) setCompletedNodes(new Set()) })
    } else {
      try {
        const raw = localStorage.getItem(progressKey(selectedCareer))
        setCompletedNodes(new Set(raw ? JSON.parse(raw) : []))
      } catch { setCompletedNodes(new Set()) }
    }
    return () => { cancelled = true }
  }, [selectedCareer, user])

  // Toggle one node optimistically, then persist. For logged-in users a failed save
  // reconciles from the server (the source of truth), so the badge never lies about
  // what was stored. saveSeq guards against out-of-order results from rapid toggles:
  // only the latest toggle's reconciliation is applied.
  const toggleComplete = (nodeId) => {
    setCompletedNodes((prev) => {
      const next = new Set(prev)
      next.has(nodeId) ? next.delete(nodeId) : next.add(nodeId)
      if (user) {
        const seq = ++saveSeqRef.current
        saveRoadmapProgress(selectedCareer, [...next]).catch(() => {
          fetchRoadmapProgress(selectedCareer)
            .then((d) => { if (seq === saveSeqRef.current) setCompletedNodes(new Set(d.completed_nodes || [])) })
            .catch(() => {})
        })
      } else {
        try { localStorage.setItem(progressKey(selectedCareer), JSON.stringify([...next])) } catch { /* ignore */ }
      }
      return next
    })
  }

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

  // Progress = completed / total across all nodes (ignores collapse). Intersect with
  // the loaded roadmap so stale ids from old data can't inflate the count.
  const allNodeIds = sections.flatMap((s) => s.nodes.map((n) => n.id))
  const totalNodes = allNodeIds.length
  const completedCount = allNodeIds.filter((id) => completedNodes.has(id)).length
  const progressPct = totalNodes ? Math.round((completedCount / totalNodes) * 100) : 0

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

  // Flat node offsets per section, so the reveal stagger runs left-to-right
  // across the whole pipeline.
  const sectionOffsets = []
  sections.reduce((acc, s) => { sectionOffsets.push(acc); return acc + s.nodes.length }, 0)

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

          {/* Progress bar */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-2">
              <span className="font-body text-eyebrow font-semibold uppercase text-navy/45">
                Your Progress
              </span>
              <span className="font-body text-small font-semibold text-navy/70 tabular">
                {completedCount} of {totalNodes} completed · <span className="text-gold">{progressPct}%</span>
              </span>
            </div>
            <div className="h-2 bg-navy/[0.1] rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-gold to-gold-light rounded-full"
                initial={false}
                animate={{ width: `${progressPct}%` }}
                transition={{ type: 'spring', stiffness: 120, damping: 24 }}
              />
            </div>
          </div>

          {/* Legend (DEV-46): what the three status colors mean, plus the
              separate gold "marked complete" decoration. */}
          <div className="flex justify-center mb-6">
            <Legend />
          </div>

          {/* Pipeline canvas */}
          <div className="relative">
            <div className="overflow-x-auto pb-4 pt-4">
              {/* DEV-47: sections as left-to-right pipeline stages with a tall
                  vertical divider between each — scales to any section count. */}
              <div key={selectedCareer} className="flex items-stretch w-max mx-auto px-2">
                {sections.map((section, si) => {
                  const isCollapsed = !!collapsed[section.id]
                  const Chevron = isCollapsed ? ChevronRight : ChevronDown
                  return (
                    <Fragment key={section.id}>
                      {si > 0 && (
                        <div className="w-[2px] self-stretch rounded-full bg-gold opacity-40 mx-6 shrink-0" aria-hidden="true" />
                      )}
                      <div className="flex flex-col gap-3 min-w-[220px] shrink-0">
                        {/* Section header — clickable to collapse */}
                        <button
                          onClick={() => toggleSection(section.id)}
                          className="focus-ring flex items-center justify-between gap-2 px-4 py-3 mb-2 rounded-md bg-navy/[0.06] hover:bg-navy/[0.10] border border-navy/[0.12] hover:border-gold/45 transition-colors duration-fast"
                        >
                          <span className="font-body text-[13px] font-semibold text-navy">
                            {section.label}
                          </span>
                          <Chevron size={15} className="text-navy/55 shrink-0" aria-hidden="true" />
                        </button>

                        {/* Stage nodes */}
                        {!isCollapsed && section.nodes.map((node, ni) => {
                          const status = nodeStatus(node, completedNodes, matchedSkills, missingSkills)
                          return (
                            <NodeButton
                              key={node.id}
                              node={node}
                              status={status}
                              isCompleted={completedNodes.has(node.id)}
                              isActive={drawerNode?.id === node.id}
                              delay={(sectionOffsets[si] + ni) * 0.06}
                              onClick={() => handleNodeClick(node)}
                            />
                          )
                        })}
                      </div>
                    </Fragment>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      </section>

      <NodeDrawer
        node={drawerNode}
        status={drawerNode ? nodeStatus(drawerNode, completedNodes, matchedSkills, missingSkills) : 'next'}
        onClose={() => setDrawerNode(null)}
        isCompleted={drawerNode ? completedNodes.has(drawerNode.id) : false}
        onToggleComplete={() => drawerNode && toggleComplete(drawerNode.id)}
      />
    </>
  )
}

export default Roadmap
