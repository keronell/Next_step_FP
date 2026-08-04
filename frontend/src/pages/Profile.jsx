import { useEffect, useRef, useState } from 'react'
import {
  Briefcase, FolderGit2, Sparkles, Plus, Trash2, X,
  ChevronRight, SkipForward, Check, AlertTriangle,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Button from '../components/ui/Button.jsx'
import { EMPTY_PROFILE, fetchProfile, isProfileEmpty, saveProfile } from '../api'
import { useAuth } from '../contexts/AuthContext'

// Shared field styling, lifted verbatim from AuthModal so the two forms can't drift.
const FIELD =
  'w-full px-4 py-3 rounded-xl border border-navy/[0.14] bg-cream/60 font-body text-body ' +
  'text-navy placeholder:text-navy/35 focus:outline-none focus:ring-2 focus:ring-gold/50 ' +
  'focus:border-gold/60 transition-all duration-base'
const LABEL = 'font-body text-small font-medium text-navy/70'

// Mirrors the server caps (common/models/profile.py) so the UI stops you at the
// same place the API would, instead of letting you type into a 422.
const MAX_ENTRIES = 10
const MAX_SKILLS = 40


const BLANK_EXPERIENCE = { role: '', context: '', duration_months: '', description: '' }
const BLANK_PROJECT = { name: '', description: '', technologies: [] }
const MAX_MONTHS = 720

// The profile store is OPTIONAL; matching is not. Neither request may hold the
// assessment hostage, so both are bounded and fall through to the same degraded
// paths a real failure takes (empty form + notice on read, continue-anyway on
// write).
//
// ABORT rather than merely stop waiting: storage is last-write-wins, so a PUT left
// running past its timeout can land after a LATER save and silently revert it.
//
// ponytail: abort closes the window from the client side only — a request the
// server already received may still commit late. Eliminating that needs
// server-side versioning (reject writes older than the stored updated_at), which
// is not worth a stored procedure until someone actually hits it.
const REQUEST_TIMEOUT_MS = 5000

async function withTimeout(run, ms = REQUEST_TIMEOUT_MS) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), ms)
  try {
    return await run(controller.signal)
  } finally {
    clearTimeout(timer)
  }
}

// The API wants int|null. `min`/`max` on <input type="number"> are only enforced by
// native form validation, which a button-driven submit never triggers — so "-5",
// "3.5" and "9999" all reach us and would 422 BOTH the PUT and the questionnaire
// POST, which the app would then read as "backend down" and answer with offline
// results. Clamp instead of rejecting: nobody needs an error dialog to be told that
// 61 years is not a duration.
function normalizeMonths(value) {
  if (value === '' || value == null) return null
  const months = Math.round(Number(value))
  if (!Number.isFinite(months)) return null
  return Math.min(MAX_MONTHS, Math.max(0, months))
}

function Profile({ phase, onComplete, onSkip }) {
  const { user } = useAuth()
  const [profile, setProfile] = useState(EMPTY_PROFILE)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  // The prefill failed, so an empty form means "we could not read your profile",
  // NOT "the user cleared it". The two are indistinguishable in `profile` alone,
  // and conflating them lets one transient GET failure erase saved data.
  const [loadFailed, setLoadFailed] = useState(false)

  // Monotonic id for the current run, bumped on every phase/user change. An async
  // handler captures it at click time and re-reads it after its await to tell
  // whether the run it belongs to is still the one on screen.
  //
  // Comparing user + phase instead is NOT enough: reset, then reach the profile
  // step again under the same account, and both match again — so a still-pending
  // save from the abandoned run would resume into the new one and submit the
  // previous quiz's answers. Only a per-run token distinguishes those.
  const runIdRef = useRef(0)

  // Prefill from the saved profile - this is what "persists across sessions" means
  // to the user. A failure here is not worth blocking on: they just start empty.
  //
  // This component is never unmounted (it returns null off-phase), so `profile`
  // survives between runs and across sign-ins. Reset it BEFORE the fetch and on
  // failure, or the previous account's experience renders while the request is in
  // flight - and stays on screen forever if the request fails.
  useEffect(() => {
    // A new run epoch: invalidates any in-flight continuation from the previous
    // one, and drops its pending state. Without clearing `saving`, abandoning a
    // run mid-PUT leaves the NEXT run's Skip and Continue disabled until that
    // request settles — forever if it hangs.
    runIdRef.current += 1
    setSaving(false)
    setLoadFailed(false)

    // Drop the account-specific form when LEAVING, not just when entering. This
    // component is never unmounted, and effects run after paint — so state kept
    // past sign-out would be painted for the NEXT account for a frame before the
    // entering branch below could clear it, briefly showing them someone else's
    // experience with Continue enabled on it.
    if (phase !== 'profiling') {
      setProfile(EMPTY_PROFILE)
      setLoading(true)
      return
    }

    let cancelled = false
    setProfile(EMPTY_PROFILE)
    if (!user) { setLoading(false); return }
    setLoading(true)
    withTimeout((signal) => fetchProfile(signal))
      .then((saved) => { if (!cancelled) setProfile({ ...EMPTY_PROFILE, ...saved }) })
      // A hang is indistinguishable from a failure here, and both must land on the
      // same screen: an empty form plus the "we couldn't load it" notice, which is
      // already wired to suppress the overwrite.
      .catch(() => { if (!cancelled) { setProfile(EMPTY_PROFILE); setLoadFailed(true) } })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [phase, user])

  if (phase !== 'profiling') return null

  const patch = (changes) => setProfile((p) => ({ ...p, ...changes }))

  const handleContinue = async () => {
    if (saving || loading) return
    const runId = runIdRef.current
    setSaving(true)
    // Drop half-filled cards: `role` and `name` are required server-side, so an
    // empty card 422s the PUT *and* the questionnaire submit — which the app would
    // read as "backend down" and answer with offline results. A card with no role
    // carries no information anyway, so there is nothing to warn about.
    const cleaned = {
      experience: profile.experience
        .filter((e) => e.role.trim())
        .map((e) => ({ ...e, duration_months: normalizeMonths(e.duration_months) })),
      projects: profile.projects.filter((p) => p.name.trim()),
      skills: profile.skills,
    }
    let stored = cleaned
    try {
      // PUT even when empty: an empty document is how the API expresses deletion,
      // so skipping the call would resurrect a profile the user just cleared.
      //
      // The one exception is an empty form we never managed to LOAD — writing that
      // would turn a transient read failure into permanent data loss. A form the
      // user actually typed into still saves: that is a deliberate overwrite.
      if (user && !(loadFailed && isProfileEmpty(cleaned))) {
        stored = await withTimeout((signal) => saveProfile(cleaned, signal))
      }
    } catch {
      // Persistence is best-effort here, exactly like submission persistence: a
      // failed OR SLOW save must never cost the user their results. On timeout we
      // carry on with the client-side `cleaned` copy, which differs from the stored
      // one only by server-side dedupe/caps the UI already applies.
      console.warn('Could not save profile; continuing with it for this run')
    }

    // The save may have outlived its run: signing out, switching account or
    // resetting during a slow PUT leaves this closure holding the PREVIOUS run's
    // onComplete, whose captured `answers` are still non-null. Calling it would
    // submit the departed run's answers over whatever is on screen now. The PUT
    // itself is fine to let finish — only the continuation must be abandoned, and
    // `saving` is owned by the current run (the effect already cleared it).
    if (runIdRef.current !== runId) return

    setSaving(false)
    onComplete(isProfileEmpty(stored) ? null : stored)
  }

  return (
    <section id="profile" className="py-24 px-6">
      <div className="max-w-3xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="bg-white rounded-card border border-navy/[0.08] shadow-lg overflow-hidden"
        >
          <div className="h-1 bg-gradient-to-r from-gold to-gold-light" />

          <div className="px-8 pt-8 pb-5 border-b border-navy/[0.06]">
            <h2 className="font-display font-bold text-h2 md:text-h1 text-navy tracking-tight text-balance">
              Tell us what you’ve <span className="italic text-gold">already done</span>
            </h2>
            <p className="font-body text-body text-navy/65 mt-3 leading-snug max-w-[56ch]">
              Your experience, projects and skills sharpen the match and highlight the real
              gaps in your roadmap. Skip it and your answers alone decide the result.
            </p>
          </div>

          {/* Without this the user sees an empty form where their saved profile
              should be and assumes it was lost. Says plainly that nothing will be
              overwritten, which is what handleContinue actually guarantees. */}
          {loadFailed && (
            <div
              role="alert"
              className="mx-8 mt-5 p-4 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-2.5"
            >
              <AlertTriangle size={16} className="text-amber-500 flex-shrink-0 mt-0.5" aria-hidden="true" />
              <p className="font-body text-small text-amber-800 leading-snug">
                We couldn’t load your saved profile just now. You can still fill this in for
                these results — anything already saved stays untouched unless you enter something new.
              </p>
            </div>
          )}

          {loading ? (
            <div className="px-8 py-16 text-center font-body text-small text-navy/50">
              Loading your profile…
            </div>
          ) : (
            <div className="divide-y divide-navy/[0.06]">
              <ExperienceSection
                entries={profile.experience}
                onChange={(experience) => patch({ experience })}
              />
              <ProjectSection
                entries={profile.projects}
                onChange={(projects) => patch({ projects })}
              />
              <SkillSection
                skills={profile.skills}
                onChange={(skills) => patch({ skills })}
              />
            </div>
          )}

          {/* Skip stays live during the prefill: it submits `null` and depends on
              nothing being fetched, so an outage in the OPTIONAL profile store must
              never be able to strand someone mid-assessment. Continue does depend on
              the loaded state, so it waits. Neither may fire mid-save. */}
          <div className="px-6 py-5 border-t border-navy/[0.06] bg-cream/60 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <Button
              variant="secondary"
              size="md"
              onClick={onSkip}
              disabled={saving}
              className="!rounded-xl"
            >
              Skip for now
              <SkipForward size={15} aria-hidden="true" />
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={handleContinue}
              loading={saving}
              disabled={loading}
              className="!rounded-xl flex-1 sm:flex-none"
            >
              Continue to results
              <ChevronRight size={15} aria-hidden="true" />
            </Button>
          </div>
        </motion.div>
      </div>
    </section>
  )
}

// ─── Section shell ─────────────────────────────────────────────────────────────

function Section({ icon: Icon, title, hint, count, children }) {
  return (
    <div className="px-8 py-7">
      <div className="flex items-start gap-3 mb-5">
        <span className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-gold/[0.12] border border-gold/30">
          <Icon size={16} className="text-gold" aria-hidden="true" />
        </span>
        <div className="flex-1 min-w-0">
          <h3 className="font-display font-semibold text-h3 text-navy tracking-tight">
            {title}
            {count > 0 && (
              <span className="ml-2 font-body text-small font-normal text-navy/45 tabular">
                {count}
              </span>
            )}
          </h3>
          <p className="font-body text-small text-navy/55 leading-snug mt-0.5">{hint}</p>
        </div>
      </div>
      {children}
    </div>
  )
}

function AddButton({ onClick, disabled, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`focus-ring inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-dashed font-body text-small font-medium transition-all duration-fast ${
        disabled
          ? 'border-navy/10 text-navy/30 cursor-not-allowed'
          : 'border-navy/20 text-navy/65 hover:border-gold/60 hover:text-navy hover:bg-gold/[0.05]'
      }`}
    >
      <Plus size={14} aria-hidden="true" />
      {children}
    </button>
  )
}

function RemoveButton({ onClick, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="focus-ring flex-shrink-0 p-2 rounded-lg text-navy/35 hover:text-red-600 hover:bg-red-50 transition-all duration-fast"
    >
      <Trash2 size={15} aria-hidden="true" />
    </button>
  )
}

// Rows animate in/out; `key` is the index because entries have no stable id and
// reordering is not a feature here.
function EntryCard({ children, onRemove, removeLabel }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0, marginBottom: 0 }}
      transition={{ duration: 0.2 }}
      className="rounded-2xl border border-navy/10 bg-cream/40 p-4 mb-3"
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0 flex flex-col gap-3">{children}</div>
        <RemoveButton onClick={onRemove} label={removeLabel} />
      </div>
    </motion.div>
  )
}

// ─── Experience ────────────────────────────────────────────────────────────────

function ExperienceSection({ entries, onChange }) {
  const update = (i, changes) =>
    onChange(entries.map((e, j) => (j === i ? { ...e, ...changes } : e)))

  return (
    <Section
      icon={Briefcase}
      title="Experience"
      hint="Jobs, internships, freelance or army roles — anything you were paid or trained to do."
      count={entries.length}
    >
      <AnimatePresence initial={false}>
        {entries.map((entry, i) => (
          <EntryCard
            key={i}
            onRemove={() => onChange(entries.filter((_, j) => j !== i))}
            removeLabel={`Remove experience ${i + 1}`}
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <label htmlFor={`exp-role-${i}`} className={LABEL}>Role</label>
                <input
                  id={`exp-role-${i}`}
                  className={FIELD}
                  value={entry.role}
                  onChange={(e) => update(i, { role: e.target.value })}
                  placeholder="Backend Developer"
                  maxLength={120}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor={`exp-context-${i}`} className={LABEL}>Where</label>
                <input
                  id={`exp-context-${i}`}
                  className={FIELD}
                  value={entry.context}
                  onChange={(e) => update(i, { context: e.target.value })}
                  placeholder="a fintech startup"
                  maxLength={120}
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor={`exp-months-${i}`} className={LABEL}>
                Duration <span className="font-normal text-navy/40">(months)</span>
              </label>
              <input
                id={`exp-months-${i}`}
                type="number"
                min={0}
                max={720}
                className={`${FIELD} sm:max-w-[9rem]`}
                value={entry.duration_months ?? ''}
                onChange={(e) => update(i, { duration_months: e.target.value })}
                placeholder="24"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor={`exp-desc-${i}`} className={LABEL}>
                What you did <span className="font-normal text-navy/40">(optional)</span>
              </label>
              <textarea
                id={`exp-desc-${i}`}
                rows={2}
                className={`${FIELD} resize-y`}
                value={entry.description}
                onChange={(e) => update(i, { description: e.target.value })}
                placeholder="built REST APIs and owned the payments service"
                maxLength={600}
              />
            </div>
          </EntryCard>
        ))}
      </AnimatePresence>

      <AddButton
        onClick={() => onChange([...entries, { ...BLANK_EXPERIENCE }])}
        disabled={entries.length >= MAX_ENTRIES}
      >
        {entries.length ? 'Add another role' : 'Add a role'}
      </AddButton>
    </Section>
  )
}

// ─── Projects ──────────────────────────────────────────────────────────────────

function ProjectSection({ entries, onChange }) {
  const update = (i, changes) =>
    onChange(entries.map((e, j) => (j === i ? { ...e, ...changes } : e)))

  return (
    <Section
      icon={FolderGit2}
      title="Projects"
      hint="Course work, side projects, hackathons — anything you built, shipped or broke."
      count={entries.length}
    >
      <AnimatePresence initial={false}>
        {entries.map((entry, i) => (
          <EntryCard
            key={i}
            onRemove={() => onChange(entries.filter((_, j) => j !== i))}
            removeLabel={`Remove project ${i + 1}`}
          >
            <div className="flex flex-col gap-1.5">
              <label htmlFor={`proj-name-${i}`} className={LABEL}>Project name</label>
              <input
                id={`proj-name-${i}`}
                className={FIELD}
                value={entry.name}
                onChange={(e) => update(i, { name: e.target.value })}
                placeholder="Course scheduling app"
                maxLength={120}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor={`proj-desc-${i}`} className={LABEL}>
                What it does <span className="font-normal text-navy/40">(optional)</span>
              </label>
              <textarea
                id={`proj-desc-${i}`}
                rows={2}
                className={`${FIELD} resize-y`}
                value={entry.description}
                onChange={(e) => update(i, { description: e.target.value })}
                placeholder="scrapes the timetable and suggests conflict-free schedules"
                maxLength={600}
              />
            </div>
            <TagInput
              id={`proj-tech-${i}`}
              label="Technologies used"
              placeholder="React, PostgreSQL…"
              tags={entry.technologies}
              max={20}
              onChange={(technologies) => update(i, { technologies })}
            />
          </EntryCard>
        ))}
      </AnimatePresence>

      <AddButton
        onClick={() => onChange([...entries, { ...BLANK_PROJECT, technologies: [] }])}
        disabled={entries.length >= MAX_ENTRIES}
      >
        {entries.length ? 'Add another project' : 'Add a project'}
      </AddButton>
    </Section>
  )
}

// ─── Skills ────────────────────────────────────────────────────────────────────

function SkillSection({ skills, onChange }) {
  return (
    <Section
      icon={Sparkles}
      title="Skills"
      hint="Languages, tools and frameworks you can already use. These carry the most weight."
      count={skills.length}
    >
      <TagInput
        id="skills"
        label="Your skills"
        placeholder="Python, SQL, Figma…"
        tags={skills}
        max={MAX_SKILLS}
        onChange={onChange}
      />
    </Section>
  )
}

// ─── Tag input (skills + project technologies) ─────────────────────────────────

function TagInput({ id, label, placeholder, tags, max, onChange }) {
  const [draft, setDraft] = useState('')
  const atCap = tags.length >= max

  const add = () => {
    // One paste can carry a whole list, so split on commas rather than making the
    // user press Enter per skill.
    const parts = draft.split(',').map((s) => s.trim()).filter(Boolean)
    if (!parts.length) return
    const existing = new Set(tags.map((t) => t.toLowerCase()))
    const next = [...tags]
    for (const part of parts) {
      if (next.length >= max) break
      if (existing.has(part.toLowerCase())) continue
      existing.add(part.toLowerCase())
      next.push(part.slice(0, 60))
    }
    onChange(next)
    setDraft('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      add()
    } else if (e.key === 'Backspace' && !draft && tags.length) {
      onChange(tags.slice(0, -1))
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className={LABEL}>
        {label}
        {atCap && <span className="ml-2 font-normal text-navy/40">(max {max})</span>}
      </label>

      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-1">
          <AnimatePresence initial={false}>
            {tags.map((tag) => (
              <motion.span
                key={tag}
                layout
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.15 }}
                // Badge's pill styling, but NOT its uppercase: skill casing carries
                // meaning (PostgreSQL, PyTorch, C#) and "PowerBI" typed back as
                // "POWERBI" reads like the app corrected them.
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-body text-small bg-gold/15 text-navy border border-gold/30"
              >
                {tag}
                <button
                  type="button"
                  onClick={() => onChange(tags.filter((t) => t !== tag))}
                  aria-label={`Remove ${tag}`}
                  className="focus-ring rounded-full p-0.5 text-navy/45 hover:text-navy transition-colors duration-fast"
                >
                  <X size={11} aria-hidden="true" />
                </button>
              </motion.span>
            ))}
          </AnimatePresence>
        </div>
      )}

      <div className="flex gap-2">
        <input
          id={id}
          className={FIELD}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          // Commit a half-typed tag instead of silently dropping it when the user
          // tabs away or clicks Continue.
          onBlur={add}
          placeholder={atCap ? '' : placeholder}
          disabled={atCap}
          maxLength={200}
        />
        <button
          type="button"
          onClick={add}
          disabled={atCap || !draft.trim()}
          aria-label={`Add ${label.toLowerCase()}`}
          className={`focus-ring flex-shrink-0 px-4 rounded-xl border font-body text-small font-semibold transition-all duration-fast ${
            atCap || !draft.trim()
              ? 'border-navy/10 text-navy/30 cursor-not-allowed'
              : 'border-gold/45 text-navy hover:bg-gold/[0.08]'
          }`}
        >
          <Check size={15} aria-hidden="true" />
        </button>
      </div>
      <p className="font-body text-eyebrow text-navy/40 normal-case tracking-normal">
        Press Enter or comma to add
      </p>
    </div>
  )
}

export default Profile
