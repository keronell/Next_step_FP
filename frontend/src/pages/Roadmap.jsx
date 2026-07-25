import { useRef, useEffect, useState } from 'react'
import { ExternalLink, X, Check, ChevronDown, ChevronRight, Flame, Star } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { ROADMAPS } from '../data'
import { fetchRoadmap, fetchRoadmapProgress, saveRoadmapProgress } from '../api'

// DEV-66: ink for the dotted connectors (rails + stubs). An explicit color-mix
// rather than `border-gold opacity-60`, because opacity on the grid cell would
// fade the node card sitting inside it too - and `border-gold/60` emits nothing
// at all (the color tokens are plain CSS-var strings with no <alpha-value>).
const TRACK_GOLD = 'color-mix(in srgb, var(--color-gold) 60%, var(--color-cream))'

// One segment of the gold spine: header -> its rail, and stage -> next stage.
// DEV-81: only the stage -> stage drop carries a chevron. The header -> nodes drop
// means "this stage contains these", not "then do these", so it stays a plain line.
const Drop = ({ arrow = false }) => (
  <div className="flex flex-col items-center" aria-hidden="true">
    <div className="h-6 w-0 shrink-0 border-l-2 border-gold" />
    {arrow && <ChevronDown size={16} strokeWidth={2.5} className="-mt-[9px] text-gold" />}
  </div>
)

// DEV-81: a node's position within its stage. Same 18px disc as the completion
// check on the opposite corner, in navy so it reads as part of the stage system
// rather than adding a fourth meaning to the three status colors.
const NumBadge = ({ ordinal, className = '' }) => (
  <span
    className={`inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full border border-cream bg-navy px-1 font-body text-[10px] font-bold leading-none text-cream ${className}`}
  >
    {ordinal}
  </span>
)

// DEV-58: one status system, one meaning per color. Green comes ONLY from the
// user ticking "Mark as complete" (so unchecking always reverts it); orange
// marks assessment skill gaps worth focusing on; everything else is neutral.
const STATUS_COLORS = {
  todo:  '#64748B', // slate  - not started
  focus: '#F97316', // orange - skill gap flagged by your assessment
  done:  '#22C55E', // green  - marked complete by you
}

const STATUS_LABELS = {
  todo:  'Not started',
  focus: 'Skill gap - focus here',
  done:  'Completed by you',
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

// DEV-59: job-ad-derived nodes carry a `demand` payload rendered as an outer frame +
// badge. Harmonized to the brand accents - navy for "In Demand", gold for "Advantage" -
// so the market frames sit distinctly on top of the soft node-state tints.
const DEMAND_COLORS = {
  required:  '#0F1B2D', // navy - In Demand (required in job ads)
  advantage: '#C9A84C', // gold - Advantage (nice-to-have edge)
}

const DEMAND_BADGE = {
  required:  'In demand',
  advantage: 'Advantage',
}

const DEMAND_LEGEND = {
  required:  'In demand - required in job ads',
  advantage: 'Advantage - nice-to-have',
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

// DEV-58: completion is the only way a node turns green, so unchecking always
// reverts it. matched_skills no longer color the canvas (that made green
// ambiguous); they surface as a hint in the node drawer instead.
function nodeStatus(node, completedNodes, missingSkills) {
  if (completedNodes.has(node.id)) return 'done'
  if (skillHits(missingSkills, node.label)) return 'focus'
  return 'todo'
}

function NodeButton({ node, status, isActive, delay, ordinal, onClick }) {
  const color = STATUS_COLORS[status]
  const isCompleted = status === 'done'
  const demand = node.demand

  // DEV-66: the reveal rides the OUTER element (see the two returns below), so a
  // market-framed node fades in frame-and-all instead of showing an empty frame
  // for 400ms. whileInView, not animate: the stack is now taller than the
  // viewport, so a mount-time stagger would play out of sight for most stages.
  const reveal = {
    initial: { opacity: 0, y: 8 },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true, amount: 0.3 },
    transition: { duration: 0.4, delay },
  }

  const button = (
    <motion.button
      onClick={onClick}
      whileHover={{ scale: 1.04 }}
      className="focus-ring relative w-full rounded-md px-3 py-2 font-body text-[13px] font-medium text-center cursor-pointer"
      // Every card gets the same treatment - an opaque soft tint of its status
      // color (color-mix with cream, so the spine can't show through) with
      // a stronger tint border; status is carried by hue, never fill-vs-outline.
      // Navy labels keep WCAG AA contrast (>10:1 on these tints). Node type
      // (required / good-to-know / optional) shows only as badges in the drawer.
      style={{
        background: `color-mix(in srgb, ${color} 18%, var(--color-cream))`,
        border: `1px solid color-mix(in srgb, ${color} 55%, var(--color-cream))`,
        color: 'var(--color-navy)',
        boxShadow: isActive ? `0 0 12px ${color}80` : undefined,
      }}
    >
      {/* DEV-81: plain text, no aria-hidden - it joins the button's accessible
          name ("2 HTML"), so the order also reaches users who never see the row.
          Nodes in the job-ad stages get no ordinal: they are ranked by demand,
          not sequenced, and the absence is what says "any order". */}
      {ordinal != null && <NumBadge ordinal={ordinal} className="absolute -top-2 -left-2" />}
      {node.label}
      {isCompleted && (
        <span
          aria-label="Marked complete"
          className="absolute -top-2 -right-2 w-[18px] h-[18px] rounded-full border border-cream flex items-center justify-center"
          style={{ background: STATUS_COLORS.done }}
        >
          <Check size={11} strokeWidth={3} className="text-cream" aria-hidden="true" />
        </span>
      )}
    </motion.button>
  )

  // w-full: the card fills its grid cell, so the rail above the row lines up with
  // the cards' outer edges instead of overhanging a sparse row of floating pills.
  if (!demand) return <motion.div {...reveal} className="w-full">{button}</motion.div>

  // DEV-59: a job-ad-derived skill - wrap the node in a brand "market" frame + badge.
  // The node still fills with its state tint, so an in-demand skill you've completed
  // reads green inside the frame.
  const dColor = DEMAND_COLORS[demand.classification] ?? DEMAND_COLORS.advantage
  const DemandIcon = demand.classification === 'required' ? Flame : Star
  const badgeText =
    demand.classification === 'required' ? `In demand · ${demand.pct}%` : 'Advantage'
  return (
    <motion.div
      {...reveal}
      className="flex w-full flex-col items-center gap-1.5 rounded-lg p-1.5"
      style={{ border: `1.5px solid ${dColor}`, background: `${dColor}0F` }}
    >
      <span
        className="inline-flex items-center justify-center gap-1 px-2 py-0.5 rounded-full text-eyebrow font-semibold uppercase leading-none"
        style={{ background: `${dColor}1F`, color: dColor }}
      >
        <DemandIcon size={11} strokeWidth={2.5} aria-hidden="true" />
        {badgeText}
      </span>
      {button}
    </motion.div>
  )
}

function NodeDrawer({ node, status, isMatchedSkill, onClose, isCompleted, onToggleComplete }) {
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
              {node.demand && (
                <span
                  className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-eyebrow font-semibold uppercase"
                  style={{
                    background: `${DEMAND_COLORS[node.demand.classification]}1F`,
                    color: DEMAND_COLORS[node.demand.classification],
                    border: `1px solid ${DEMAND_COLORS[node.demand.classification]}40`,
                  }}
                >
                  {node.demand.classification === 'required' ? (
                    <Flame size={11} strokeWidth={2.5} aria-hidden="true" />
                  ) : (
                    <Star size={11} strokeWidth={2.5} aria-hidden="true" />
                  )}
                  {DEMAND_BADGE[node.demand.classification]}
                </span>
              )}
            </div>

            <h3 className="font-display font-semibold text-h3 text-navy mb-3 tracking-tight">
              {node.label}
            </h3>

            <p className="font-body text-small text-navy/65 leading-relaxed mb-6">
              {node.description}
            </p>

            {/* DEV-58: matched_skills no longer color the canvas green - the hint
                that the assessment already saw this skill lives here instead. */}
            {isMatchedSkill && !isCompleted && (
              <p
                className="font-body text-small text-navy/65 leading-relaxed mb-6 px-3 py-2 rounded-lg"
                style={{
                  background: 'color-mix(in srgb, var(--color-navy) 4%, var(--color-cream))',
                  border: '1px solid color-mix(in srgb, var(--color-navy) 12%, var(--color-cream))',
                }}
              >
                Your assessment suggests you already have this skill - mark it
                complete if that sounds right.
              </p>
            )}

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
            className="relative w-[26px] h-[14px] rounded shrink-0"
            style={{
              background: `color-mix(in srgb, ${STATUS_COLORS[status]} 18%, var(--color-cream))`,
              border: `1px solid color-mix(in srgb, ${STATUS_COLORS[status]} 55%, var(--color-cream))`,
            }}
          >
            {status === 'done' && (
              <span
                className="absolute -top-1.5 -right-1.5 w-[12px] h-[12px] rounded-full border border-cream flex items-center justify-center"
                style={{ background: STATUS_COLORS.done }}
              >
                <Check size={8} strokeWidth={3.5} className="text-cream" aria-hidden="true" />
              </span>
            )}
          </span>
          <span className="font-body text-small text-navy/70 whitespace-nowrap">
            {STATUS_LABELS[status]}
          </span>
        </div>
      ))}
      {/* DEV-59: the two job-ad "market" frames (badge + outer frame on a node). */}
      <div className="flex items-center gap-x-4 gap-y-2 flex-wrap pl-5 border-l border-navy/[0.08]">
        {Object.keys(DEMAND_COLORS).map((cls) => (
          <div key={cls} className="flex items-center gap-2">
            <span
              className="w-[26px] h-[14px] rounded shrink-0"
              style={{ border: `1.5px solid ${DEMAND_COLORS[cls]}`, background: `${DEMAND_COLORS[cls]}1F` }}
            />
            <span className="font-body text-small text-navy/70 whitespace-nowrap">
              {DEMAND_LEGEND[cls]}
            </span>
          </div>
        ))}
      </div>
      {/* DEV-81: the only place the "unnumbered = any order" rule can be stated. */}
      <div className="flex items-center gap-2">
        <span className="flex items-center gap-0.5 shrink-0">
          {[1, 2, 3].map((n) => <NumBadge key={n} ordinal={n} />)}
        </span>
        {/* Both halves, or the rule isn't stated: an unnumbered card is a
            deliberate "any order", not a number someone forgot. No
            whitespace-nowrap here (unlike the short rows above) - this copy is
            long enough to overflow the legend on a phone if it can't wrap. */}
        <span className="font-body text-small text-navy/70">
          Numbered - learn in this order; unnumbered - any order
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

  // Load completed nodes for this career from Supabase. <Roadmap> only ever mounts
  // for a signed-in user now (DEV-82: RoadmapPage walls everyone else out), so progress
  // is always server-backed — no anonymous localStorage path.
  useEffect(() => {
    if (!selectedCareer) { setCompletedNodes(new Set()); return }
    let cancelled = false
    fetchRoadmapProgress(selectedCareer)
      .then((d) => { if (!cancelled) setCompletedNodes(new Set(d.completed_nodes || [])) })
      .catch(() => { if (!cancelled) setCompletedNodes(new Set()) })
    return () => { cancelled = true }
  }, [selectedCareer])

  // Toggle one node optimistically, then persist. A failed save reconciles from the
  // server (the source of truth), so the badge never lies about what was stored.
  // saveSeq guards against out-of-order results from rapid toggles: only the latest
  // toggle's reconciliation is applied.
  const toggleComplete = (nodeId) => {
    setCompletedNodes((prev) => {
      const next = new Set(prev)
      next.has(nodeId) ? next.delete(nodeId) : next.add(nodeId)
      const seq = ++saveSeqRef.current
      saveRoadmapProgress(selectedCareer, [...next]).catch(() => {
        fetchRoadmapProgress(selectedCareer)
          .then((d) => { if (seq === saveSeqRef.current) setCompletedNodes(new Set(d.completed_nodes || [])) })
          .catch(() => {})
      })
      return next
    })
  }

  // Fetch the roadmap from the backend; fall back to the bundled ROADMAPS if it's
  // down (same offline-estimate spirit as the questionnaire results). The career is
  // the ONLY input: the response is curated content plus job-ad market stages, so
  // it no longer varies with the user's gaps or profile and there is nothing else
  // to key a refetch on.
  useEffect(() => {
    if (!selectedCareer) {
      setRoadmapData(null)
      return
    }
    let cancelled = false
    fetchRoadmap(selectedCareer)
      .then((data) => { if (!cancelled) setRoadmapData(data) })
      .catch(() => { if (!cancelled) setRoadmapData(ROADMAPS[selectedCareer] ?? null) })
    return () => { cancelled = true }
  }, [selectedCareer])

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

  if (!selectedCareer) return null

  return (
    <>
      <section id="roadmap" className="pt-10 pb-24 px-6 relative">
        <div className="max-w-7xl mx-auto relative">
          {/* No heading here: RoadmapPage's hero already titles the page with this
              career (DEV-66) - this component used to be one section among many. */}

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
            {/* DEV-58: the tokens don't support alpha modifiers (bg-navy/[0.1] is a
                silent no-op), so the track gets an explicit tint + thin border -
                otherwise its extent is invisible at low progress. */}
            <div
              className="h-2.5 rounded-full overflow-hidden"
              style={{
                background: 'color-mix(in srgb, var(--color-navy) 8%, var(--color-cream))',
                border: '1px solid color-mix(in srgb, var(--color-navy) 30%, var(--color-cream))',
              }}
            >
              <motion.div
                className="h-full bg-gradient-to-r from-gold to-gold-light rounded-full"
                initial={false}
                animate={{ width: `${progressPct}%` }}
                transition={{ type: 'spring', stiffness: 120, damping: 24 }}
              />
            </div>
          </div>

          {/* Legend (DEV-58): the three node states - completion (green + check)
              is the only user-driven one, so ticking/unticking always matches. */}
          <div className="flex justify-center mb-6">
            <Legend />
          </div>

          {/* Roadmap canvas (DEV-66): stages read top-to-bottom threaded on a gold
              spine, and each stage's nodes flow left-to-right in a wrapping grid.
              Deliberately NOT roadmap.sh's left/right zigzag - see
              docs/adr/0001-vertical-stage-flow.md. No horizontal scrolling at any
              width; narrow viewports wrap instead. */}
          <div key={selectedCareer} className="flex flex-col items-center">
            {sections.map((section) => {
              const isCollapsed = !!collapsed[section.id]
              const Chevron = isCollapsed ? ChevronRight : ChevronDown
              // DEV-81: the job-ad stages inject_requirements() appends are ranked by
              // demand, not sequenced - numbering them would claim a learning order
              // the backend never meant. Static and LLM roadmaps carry no `source`.
              const ordered = section.source !== 'job_ads'
              return (
                <div key={section.id} className="flex flex-col items-center w-full">
                  {/* Stage header - a navy pill sitting on the spine, click to collapse. */}
                  <button
                    onClick={() => toggleSection(section.id)}
                    className="focus-ring inline-flex items-center gap-2 h-11 px-5 rounded-md bg-navy text-cream hover:bg-navy-light border border-navy transition-colors duration-fast"
                  >
                    <span className="font-body text-[13px] font-semibold">
                      {section.label}
                    </span>
                    <Chevron size={15} className="text-cream opacity-70 shrink-0" aria-hidden="true" />
                  </button>

                  {!isCollapsed && (
                    <>
                      <Drop />
                      {/* Node rows. Deliberately NO column gap: each cell's dotted
                          top border butts against its neighbours' to form one
                          continuous rail, and a wrapped row grows its own rail for
                          free - no row chunking, no measurement, no SVG. Horizontal
                          breathing room lives in the cells' own padding instead.
                          flex-wrap + justify-center (not a grid): grid tracks are
                          allocated for the whole grid, so a PARTIAL last row would
                          hug the left edge and its rail would never cross the centre
                          line. Centering the row fixes both. Cells grow to fill a
                          full row but cap at 340px, so a lone wrapped node doesn't
                          stretch across the whole canvas. ~5 per row at 1280px, 3 at
                          768px, 1 on a phone. */}
                      <div className="relative flex w-full flex-wrap justify-center gap-y-7">
                        {/* Threads the rails together: without this, every wrapped
                            row after the first floats detached from the spine. First
                            in DOM and the cells are `relative`, so cards paint over
                            it rather than the other way round. */}
                        <div
                          className="absolute left-1/2 top-0 bottom-0 w-0 -translate-x-1/2"
                          style={{ borderLeft: `2px dotted ${TRACK_GOLD}` }}
                          aria-hidden="true"
                        />
                        {section.nodes.map((node, ni) => (
                          <div
                            key={node.id}
                            className="relative flex max-w-[340px] grow basis-[200px] flex-col items-center px-3"
                            style={{ borderTop: `2px dotted ${TRACK_GOLD}` }}
                          >
                            {/* Stub: rail down to this node. */}
                            <div
                              className="h-4 w-0 shrink-0"
                              style={{ borderLeft: `2px dotted ${TRACK_GOLD}` }}
                              aria-hidden="true"
                            />
                            <NodeButton
                              node={node}
                              status={nodeStatus(node, completedNodes, missingSkills)}
                              isActive={drawerNode?.id === node.id}
                              // Sweeps left-to-right across the stage. Capped so a
                              // wrapped second row doesn't inherit a long delay.
                              delay={Math.min(ni, 5) * 0.05}
                              ordinal={ordered ? ni + 1 : null}
                              onClick={() => handleNodeClick(node)}
                            />
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  {/* Spine carries on to the next stage - emitted for collapsed
                      stages too, so collapsing never breaks the thread. DEV-81: its
                      chevron is the "then this" cue; on the last stage the same
                      chevron terminates the spine (it used to be a special case). */}
                  <Drop arrow />
                </div>
              )
            })}
          </div>
        </div>
      </section>

      <NodeDrawer
        node={drawerNode}
        status={drawerNode ? nodeStatus(drawerNode, completedNodes, missingSkills) : 'todo'}
        isMatchedSkill={drawerNode ? skillHits(matchedSkills, drawerNode.label) : false}
        onClose={() => setDrawerNode(null)}
        isCompleted={drawerNode ? completedNodes.has(drawerNode.id) : false}
        onToggleComplete={() => drawerNode && toggleComplete(drawerNode.id)}
      />
    </>
  )
}

export default Roadmap
