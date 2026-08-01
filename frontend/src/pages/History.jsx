import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { BarChart2, Check, Clock, Compass, Layers, Monitor, Pen, Server, Code2, Smartphone, PieChart, Brain, Sparkles, ShieldCheck, Bug, Gamepad2, FileText, Network, Trash2, Loader2, X } from 'lucide-react'
import { fetchMySubmissions, deleteSubmission } from '../api'

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

export default function History({ user, onLoadResults, onChanged }) {
  const [submissions, setSubmissions] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  // Serializes delete+refill operations (see handleDelete).
  const deleteChain = useRef(Promise.resolve())
  // Live view of who is signed in, for reading AFTER an await. Both fetches below
  // are issued with one account's token but resolve later — if the user has since
  // switched accounts, applying that response would render the PREVIOUS account's
  // assessments (and, since DEV-60, their profile snapshots) to the new one, who
  // could then open them.
  const userRef = useRef(user)
  userRef.current = user

  useEffect(() => {
    if (!user) { setSubmissions([]); return }
    setLoading(true)
    setError(false)
    const startedAs = user
    fetchMySubmissions()
      .then((subs) => { if (userRef.current === startedAs) setSubmissions(subs) })
      .catch(() => { if (userRef.current === startedAs) setError(true) })
      .finally(() => { if (userRef.current === startedAs) setLoading(false) })
  }, [user])

  // DEV-75: remove a past result. The card confirms first; here we call the API
  // (server enforces ownership), then REFETCH — the list is capped at the server's
  // HISTORY_LIMIT, so a plain local filter would shrink it and never reveal the
  // next-older submission after repeated deletes.
  //
  // Deletes are SERIALIZED through deleteChain: each delete + its refill runs to
  // completion before the next starts. Otherwise concurrent deletes each issue a
  // full-list refill that can resolve out of order, and a stale one (its snapshot
  // taken before a later delete) would reinsert an already-deleted card. Chaining
  // guarantees every refill reflects all prior deletes. The card awaits its own
  // link, so it still sees errors and can retry.
  const handleDelete = (requestId) => {
    const startedAs = user
    const run = deleteChain.current
      .catch(() => {}) // isolate this delete from a prior link's failure
      .then(async () => {
        try {
          await deleteSubmission(requestId)
        } catch (err) {
          // 404 == already gone (deleted in another tab, or a retry whose first
          // response was lost). The desired end state is reached, so converge:
          // fall through and refill rather than telling the user it failed.
          if (err?.status !== 404) throw err
        }
        try {
          const fresh = await fetchMySubmissions()
          // Dropped outright after an account switch — see userRef above.
          if (userRef.current === startedAs) {
            setSubmissions(fresh)
            // DEV-76: the deleted submission may be the one the resume pointer was
            // derived from. Hand the refreshed list up so App can recompute it —
            // otherwise the next load boots onto a career whose assessment no longer
            // exists, which `recommended-careers` then refuses, leaving the user on a
            // locked roadmap every visit with no assessment to explain it.
            onChanged?.(fresh)
          }
        } catch {
          // Delete succeeded but the refill fetch failed — at least drop the removed
          // card locally so the UI reflects the deletion.
          if (userRef.current === startedAs) {
            setSubmissions((subs) => subs.filter((s) => s.request_id !== requestId))
            // The refill that would tell us what survives is exactly what just
            // failed, so clear the pointer rather than guess. Worst case that costs
            // one un-jumped load, which then recomputes it correctly; guessing wrong
            // costs a locked roadmap that never self-corrects. Called outside the
            // updater above — that must stay pure, and StrictMode double-invokes it.
            onChanged?.(null)
          }
        }
      })
    deleteChain.current = run
    return run
  }

  if (!user) return null

  return (
    <div className="px-4 py-3">
      <p className="font-body text-eyebrow text-navy/40 uppercase font-semibold">Past assessments</p>
      <p className="font-body text-small text-navy/55 mt-0.5 mb-3">
        Career discovery results linked to your account. Click any to reload.
      </p>

      {loading && (
        <div className="flex flex-col gap-2">
          {[1, 2].map((i) => (
            <div key={i} className="h-16 rounded-xl bg-navy/[0.04] animate-pulse" />
          ))}
        </div>
      )}

      {!loading && error && (
        <p className="font-body text-small text-navy/55">
          Could not load your history right now.
        </p>
      )}

      {!loading && !error && submissions.length === 0 && (
        <p className="font-body text-small text-navy/55">
          No saved assessments yet - complete one above to see it here.
        </p>
      )}

      {!loading && !error && submissions.length > 0 && (
        <div className="flex flex-col gap-2">
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

  const load = () =>
    onLoad(
      submission.recommendations,
      submission.selected_career ?? null,
      // The profile this submission was scored with, so the restored roadmap
      // is personalized by it rather than by the current run's.
      submission.profile ?? null,
    )

  const confirmDelete = async (e) => {
    e.stopPropagation()
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
      className="relative rounded-xl bg-white border border-navy/[0.08] shadow-sm hover:border-gold/40 hover:shadow-[0_8px_24px_-8px_rgba(201,168,76,0.25)] transition-all duration-base"
    >
      {/* Whole row loads the result — simpler and more reliable than a small
          hover-revealed button, and works the same on touch as on desktop. */}
      <button
        onClick={load}
        aria-label={`Load ${top.title} results`}
        className="focus-ring w-full text-left flex items-center gap-3 px-3 py-2.5 pr-16"
      >
        <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-gold/10 border border-gold/25 flex items-center justify-center">
          <CareerIcon size={15} className="text-gold" aria-hidden="true" />
        </div>

        <div className="min-w-0 flex-1">
          <p className="font-body text-small font-semibold text-navy truncate">
            {top.title}
          </p>
          <div className="flex items-center flex-wrap gap-x-1.5 gap-y-0.5 mt-0.5">
            <span className="font-body text-xs font-bold text-gold">
              {top.matchPercent}%
            </span>
            {date && (
              <>
                <span className="text-navy/20" aria-hidden="true">·</span>
                <span className="font-body text-xs text-navy/45 inline-flex items-center gap-1">
                  <Clock size={10} aria-hidden="true" className="text-navy/30" />
                  {date}
                </span>
              </>
            )}
            {submission.recommendations.length > 1 && (
              <>
                <span className="text-navy/20" aria-hidden="true">·</span>
                <span className="font-body text-xs text-navy/45">
                  +{submission.recommendations.length - 1} more
                </span>
              </>
            )}
          </div>
          {failed && (
            <p className="font-body text-xs text-red-600 mt-0.5" role="alert">
              Couldn’t delete - try again
            </p>
          )}
        </div>
      </button>

      {/* Delete control: always visible (not hover-gated) so it works on touch and
          doesn't need extra row width reserved for a second button. */}
      <div className="absolute top-2 right-2 flex items-center gap-1">
        {confirming ? (
          <>
            <button
              onClick={() => { setConfirming(false); setFailed(false) }}
              disabled={deleting}
              aria-label="Cancel delete"
              className="focus-ring w-7 h-7 rounded-lg flex items-center justify-center text-navy/50 hover:text-navy hover:bg-navy/[0.04] transition-colors duration-fast disabled:opacity-50"
            >
              <X size={13} aria-hidden="true" />
            </button>
            <button
              onClick={confirmDelete}
              disabled={deleting}
              aria-label={`Confirm delete ${top.title} result`}
              className="focus-ring w-7 h-7 rounded-lg flex items-center justify-center text-red-600 border border-red-200 hover:bg-red-50 transition-colors duration-fast disabled:opacity-60"
            >
              {deleting
                ? <Loader2 size={12} className="animate-spin" aria-hidden="true" />
                : <Check size={12} aria-hidden="true" />}
            </button>
          </>
        ) : (
          <button
            onClick={() => setConfirming(true)}
            aria-label={`Delete ${top.title} result`}
            className="focus-ring w-7 h-7 rounded-lg flex items-center justify-center text-navy/35 hover:text-red-600 hover:bg-red-50 transition-colors duration-fast"
          >
            <Trash2 size={13} aria-hidden="true" />
          </button>
        )}
      </div>
    </motion.div>
  )
}
