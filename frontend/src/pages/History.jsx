import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { BarChart2, ChevronRight, Clock, Compass, Layers, Monitor, Pen, Server, Code2, Smartphone, PieChart, Brain, Sparkles, ShieldCheck, Bug, Gamepad2, FileText, Network, Trash2, Loader2 } from 'lucide-react'
import { fetchMySubmissions, deleteSubmission } from '../api'
import Button from '../components/ui/Button.jsx'
import SectionHeading from '../components/ui/SectionHeading.jsx'

const ICON_MAP = {
  Monitor, Server, BarChart2, Layers, Compass, Pen,
  Code2, Smartphone, PieChart, Brain, Sparkles, ShieldCheck, Bug, Gamepad2, FileText, Network,
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

export default function History({ user, onLoadResults }) {
  const [submissions, setSubmissions] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!user) { setSubmissions([]); return }
    setLoading(true)
    setError(false)
    fetchMySubmissions()
      .then(setSubmissions)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [user])

  // DEV-75: remove a past result. The card confirms first; here we call the API
  // (server enforces ownership) and drop it from the list only on success. Errors
  // propagate back to the card so it can surface a retry.
  const handleDelete = async (requestId) => {
    await deleteSubmission(requestId)
    setSubmissions((subs) => subs.filter((s) => s.request_id !== requestId))
  }

  if (!user) return null

  return (
    <section id="history" className="py-24 px-6 border-t border-navy/[0.06]">
      <div className="max-w-3xl mx-auto">
        <SectionHeading
          eyebrow="Your Account"
          title="Past assessments"
          lede="Career discovery results linked to your account. Click any to reload."
          align="left"
          className="mb-10"
        />

        {loading && (
          <div className="flex flex-col gap-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-20 rounded-card bg-navy/[0.04] animate-pulse" />
            ))}
          </div>
        )}

        {!loading && error && (
          <p className="font-body text-body text-navy/55">
            Could not load your history right now.
          </p>
        )}

        {!loading && !error && submissions.length === 0 && (
          <p className="font-body text-body text-navy/55">
            No saved assessments yet - complete one above to see it here.
          </p>
        )}

        {!loading && !error && submissions.length > 0 && (
          <div className="flex flex-col gap-3">
            {submissions.map((sub, i) => (
              <HistoryCard
                key={sub.request_id}
                submission={sub}
                index={i}
                onLoad={onLoadResults}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

function HistoryCard({ submission, index, onLoad, onDelete }) {
  const [confirming, setConfirming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [failed, setFailed] = useState(false)

  const top = submission.recommendations?.[0]
  if (!top) return null

  const CareerIcon = ICON_MAP[top.icon] || Monitor
  const date = formatDate(submission.created_at)

  const confirmDelete = async () => {
    setDeleting(true)
    setFailed(false)
    try {
      await onDelete(submission.request_id)
      // On success the parent drops this card from the list, so it unmounts here.
    } catch {
      setDeleting(false)
      setFailed(true)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4, delay: index * 0.06, ease: [0.25, 0.46, 0.45, 0.94] }}
      className="group flex items-center gap-4 rounded-card bg-white border border-navy/[0.08] px-5 py-4 shadow-sm hover:border-gold/40 hover:shadow-[0_8px_24px_-8px_rgba(201,168,76,0.25)] transition-all duration-base"
    >
      {/* Career icon */}
      <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-gold/10 border border-gold/25 flex items-center justify-center">
        <CareerIcon size={16} className="text-gold" aria-hidden="true" />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="font-body text-body font-semibold text-navy truncate">
          {top.title}
        </p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="font-body text-small font-bold text-gold">
            {top.matchPercent}%
          </span>
          {date && (
            <>
              <span className="text-navy/20" aria-hidden="true">·</span>
              <span className="font-body text-small text-navy/45 inline-flex items-center gap-1">
                <Clock size={11} aria-hidden="true" className="text-navy/30" />
                {date}
              </span>
            </>
          )}
          {submission.recommendations.length > 1 && (
            <>
              <span className="text-navy/20" aria-hidden="true">·</span>
              <span className="font-body text-small text-navy/45">
                +{submission.recommendations.length - 1} more
              </span>
            </>
          )}
          {failed && (
            <>
              <span className="text-navy/20" aria-hidden="true">·</span>
              <span className="font-body text-small text-red-600" role="alert">
                Couldn’t delete - try again
              </span>
            </>
          )}
        </div>
      </div>

      {/* Actions: default (Load + delete) vs. an inline delete confirmation. Plain
          conditional render - no per-card AnimatePresence, which swallowed the state
          toggle here. */}
      <div className="flex-shrink-0 flex items-center gap-2">
        {confirming ? (
          <>
            <span className="font-body text-small text-navy/60 hidden sm:inline">Delete?</span>
            <button
              onClick={() => { setConfirming(false); setFailed(false) }}
              disabled={deleting}
              className="focus-ring px-3 py-2 rounded-xl font-body text-small font-medium text-navy/60 hover:text-navy hover:bg-navy/[0.04] transition-colors duration-fast disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={confirmDelete}
              disabled={deleting}
              aria-label={`Confirm delete ${top.title} result`}
              className="focus-ring inline-flex items-center gap-1.5 px-3 py-2 rounded-xl font-body text-small font-semibold text-red-600 border border-red-200 hover:bg-red-50 transition-colors duration-fast disabled:opacity-60"
            >
              {deleting
                ? <Loader2 size={13} className="animate-spin" aria-hidden="true" />
                : <Trash2 size={13} aria-hidden="true" />}
              Delete
            </button>
          </>
        ) : (
          <>
            {/* Visible by default so touch users can see the actions; hidden until
                hover/focus ONLY on devices that actually support hover (@media
                hover:hover) - not merely wide ones, since md is viewport width and a
                wide tablet still can't hover. */}
            <Button
              variant="secondary"
              size="md"
              onClick={() => onLoad(submission.recommendations, submission.selected_career ?? null)}
              className="!px-4 !py-2 !text-small opacity-100 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 [@media(hover:hover)]:focus-visible:opacity-100 transition-opacity duration-fast"
              aria-label={`Load ${top.title} results`}
            >
              Load
              <ChevronRight size={13} aria-hidden="true" />
            </Button>
            <button
              onClick={() => setConfirming(true)}
              aria-label={`Delete ${top.title} result`}
              className="focus-ring inline-flex items-center justify-center w-9 h-9 rounded-xl text-navy/40 hover:text-red-600 hover:bg-red-50 transition-colors duration-fast opacity-100 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 [@media(hover:hover)]:focus-visible:opacity-100"
            >
              <Trash2 size={15} aria-hidden="true" />
            </button>
          </>
        )}
      </div>
    </motion.div>
  )
}
