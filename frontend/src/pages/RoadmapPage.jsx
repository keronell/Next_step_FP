// DEV-76 / DEV-65: standalone, deep-linkable "Your Learning Roadmap" page at
// `/roadmap/{careerId}` — the returning-user home. It renders the roadmap
// (header/footer chrome around it), deliberately bypassing the Hero, "How It
// Works", Assessment and Results sections that the scroll app (App.jsx) stacks
// above the roadmap. A returning user with a completed assessment lands here
// directly; a bare bookmark still shows the generic roadmap.
//
// The roadmap itself is the existing <Roadmap> component, reused unchanged (it
// fetches its own roadmap data + progress). This page resolves the user's
// recommendation for `careerId` — preferring the one the app already holds (the
// result the user just clicked), falling back to server history for true deep links.
// That single lookup answers both questions the page has: which skill gaps to
// highlight, and (DEV-82) whether the roadmap is unlocked at all.
import { useEffect, useState } from 'react'
import { ArrowLeft, Lock } from 'lucide-react'
import Header from '../components/Header'
import Footer from '../components/Footer'
import ParticleField from '../components/ParticleField'
import Button from '../components/ui/Button.jsx'
import AuthModal from './AuthModal'
import Roadmap from './Roadmap'
import { CAREERS } from '../data'
import { fetchMySubmissions, fetchRecommendedCareers } from '../api'
import { useAuth } from '../contexts/AuthContext'
import { navigate } from '../hooks/useRoute'

// Right after an assessment, save_submission is still a background task, so history
// can briefly report an empty eligibility set for a career the user just earned. Retry
// the eligibility check this many times, this far apart, before concluding "locked" —
// enough to ride out the sub-second persistence lag, short enough that a genuinely
// locked deep link doesn't sit on a long spinner.
const ELIGIBILITY_RETRIES = 1
const ELIGIBILITY_RETRY_MS = 1000

// The recommendation entry for a given career within a recommendations array.
function findRec(recs, careerId) {
  return (recs || []).find((r) => r.id === careerId) || null
}

// The user's recommendation for `careerId` from their (capped) submission history,
// used only for skill personalization — eligibility is decided separately, uncapped.
// Prefer the submission they actually selected, matching App.jsx's restore-latest.
function recFromHistory(subs, careerId) {
  const sorted = [...(subs || [])].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at),
  )
  const sub =
    sorted.find((s) => s.selected_career === careerId && findRec(s.recommendations, careerId)) ||
    sorted.find((s) => findRec(s.recommendations, careerId))
  return sub ? findRec(sub.recommendations, careerId) : null
}

export default function RoadmapPage({ careerId, recommendations, onStartAssessment, onLoadResults }) {
  const { user, authLoading } = useAuth()
  const [authModalOpen, setAuthModalOpen] = useState(false)

  // DEV-82: a roadmap is *unlocked* only for a career the user holds a recommendation
  // for (CONTEXT.md) — the same evidence that personalizes it also authorizes it, so
  // one lookup decides both with no extra request.
  //
  // The resolution is tagged with the inputs it was computed for, and the render below
  // trusts it only on an exact match. That is what makes a stale answer unable to
  // authorize the wrong thing: state set inside the effect lands a render LATE, so on
  // the render where `careerId` or `user` changes — sign out while the page is open, or
  // switch careers in place via App.jsx's handleLoadHistoryOnRoadmap — a plain
  // `unlocked` boolean would still read `true` and paint the roadmap for a frame.
  // Mismatch reads as "not resolved yet" and shows the spinner, so there is no gap.
  const [resolution, setResolution] = useState(null)
  const gateKey = `${careerId}|${user?.user_id ?? ''}`

  // Resolve two things for this career: is the roadmap unlocked, and which skill gaps
  // to highlight. They come from different places on purpose.
  //
  // Eligibility (unlock) is the uncapped set of careers the user was ever recommended
  // (fetchRecommendedCareers). It must be uncapped: my-submissions caps at 20, so a
  // heavy user's older recommendation would falsely lock a roadmap they earned — the
  // submission is still stored (docs/adr/0002-roadmap-access.md). Skills come from the
  // (capped) submission history, which carries the recommendation object; a career
  // unlocked but absent from the newest 20 simply renders as a plain roadmap.
  //
  // Fast path: the recommendation the app already holds (passed in when the user clicks
  // "View Roadmap" right after a submit) unlocks with no fetch — at that moment the
  // submission may not be persisted yet, so a server check could miss it.
  //
  // Fail-open: an unreachable eligibility endpoint unlocks (we can't prove the
  // recommendation, but the caller IS authenticated, and walling them would take the
  // page down for every returning user during a history outage). A failed *skills*
  // fetch just yields a plain roadmap. Signing in re-runs this (`gateKey` deps on
  // user), so the wall lifts itself.
  useEffect(() => {
    if (authLoading) return // wait for auth to settle before choosing a source
    let cancelled = false

    const apply = (rec, unlocked) => {
      if (cancelled) return
      setResolution({
        key: gateKey,
        unlocked,
        missing: rec?.missing_skills ?? [],
        matched: rec?.matched_skills ?? [],
      })
    }

    // Signed out: locked outright, and nothing worth resolving behind the wall.
    if (!user) {
      apply(null, false)
      return () => { cancelled = true }
    }

    const passed = findRec(recommendations, careerId)
    if (passed) {
      apply(passed, true)
      return () => { cancelled = true }
    }

    // Is this career in the user's uncapped recommended set? A rejected request fails
    // open (unlock). An empty-but-fulfilled result may just be persistence lag right
    // after a submit, so retry a bounded number of times before concluding locked.
    const resolveUnlocked = async () => {
      // dev-only: skip the eligibility check so working on the roadmap locally
      // doesn't cost a fresh 13-15 question assessment per career. `vite build`
      // substitutes `false` here and drops the branch, so it stays out of the
      // production bundle (verified: byte-identical output with and without this
      // line). The signed-out wall above still applies, so this narrows the DEV-82
      // gate (docs/adr/0002-roadmap-access.md) in dev rather than removing it —
      // LockedPanel's "never recommended" door is unreachable until you comment
      // this out.
      if (import.meta.env.DEV) return true

      for (let attempt = 0; ; attempt++) {
        try {
          if ((await fetchRecommendedCareers()).includes(careerId)) return true
        } catch {
          return true // eligibility unreachable -> fail open
        }
        if (attempt >= ELIGIBILITY_RETRIES) return false
        await new Promise((r) => setTimeout(r, ELIGIBILITY_RETRY_MS))
        if (cancelled) return false // ignored — apply() guards on cancelled
      }
    }

    // Skills come from the capped history in parallel; a failed fetch just drops
    // personalization (plain roadmap), independent of the unlock decision above.
    const resolveSkills = fetchMySubmissions().then(
      (subs) => recFromHistory(subs, careerId),
      () => null,
    )

    Promise.all([resolveUnlocked(), resolveSkills]).then(
      ([unlocked, rec]) => apply(rec, unlocked),
    )

    return () => { cancelled = true }
  }, [gateKey, careerId, user, authLoading, recommendations])

  // NB: we deliberately do NOT record a career selection on mount here. selectCareer
  // is scoped to the anonymous session id (which survives sign-out), so recording on
  // a mere bookmark visit could overwrite a previous signed-in user's selected_career
  // on a shared browser. Selection is recorded only from the explicit "View Roadmap"
  // click (App.jsx::handleSelectCareer).

  const career = CAREERS.find((c) => c.id === careerId)
  // Only a resolution computed for THESE inputs counts; anything else is still resolving.
  const resolved = resolution?.key === gateKey ? resolution : null
  const locked = resolved != null && !resolved.unlocked

  const goHome = () => navigate('/')

  return (
    <div className="min-h-screen bg-cream">
      <Header
        phase="idle"
        onReset={goHome}
        onOpenAuth={() => setAuthModalOpen(true)}
        onStartAssessment={onStartAssessment}
        // No shortcut on the roadmap page itself: it would point at the URL we
        // are already showing. Passing careerId here also showed "My Roadmap" to
        // any signed-in visitor opening a deep link, contradicting Header's
        // contract that it means "your latest completed assessment".
        roadmapCareerId={null}
        // Past assessments (DEV-?? relocation): only passed here, on the roadmap
        // page, so the "My History" item in the account menu expands the list
        // in-place instead of navigating (elsewhere in the app it has nowhere to
        // expand to, so Header falls back to routing here).
        onHistoryLoadResults={onLoadResults}
      />
      <AuthModal open={authModalOpen} onClose={() => setAuthModalOpen(false)} />
      <main>
        {/* DEV-80: hero tint, the same cream→#F0EAD8 wash the Landing hero paints.
            Full-bleed (outside the max-w-7xl) so it spans the viewport rather than
            banding the centre column, and fading to transparent so it dissolves into
            the cream canvas instead of ending on a seam above the roadmap. Starts
            `from-cream` for the same reason Landing's does: the header is transparent
            until scrolled, so a gradient opening on the tint draws a hard edge along
            the header's bottom. First in DOM with the content `relative`, so the
            content paints over it. */}
        <div className="relative">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 bg-gradient-to-b from-cream via-[#F0EAD8] to-transparent"
          />
          {/* The Landing hero's drifting particles, sized for this band: it is ~300px
              tall against that hero's ~900px, so it takes far fewer dots to read at the
              same density. The mask fades them out on the same curve as the tint above,
              so the field dissolves into the cream canvas rather than ending on a hard
              line of dots right above the roadmap. */}
          <ParticleField
            count={30}
            countSmall={12}
            style={{
              maskImage: 'linear-gradient(to bottom, #000 55%, transparent)',
              WebkitMaskImage: 'linear-gradient(to bottom, #000 55%, transparent)',
            }}
          />
          <div className="relative max-w-7xl mx-auto px-6 pt-24 pb-0">
            <button
              onClick={goHome}
              className="focus-ring inline-flex items-center gap-1.5 px-4 py-2 rounded-xl font-body text-small font-medium text-navy/65 hover:text-navy hover:bg-navy/[0.04] transition-all duration-fast"
            >
              <ArrowLeft size={15} aria-hidden="true" />
              Back to home
            </button>

            {/* Page hero. DEV-66: this is now the ONLY heading on the page — <Roadmap>
                used to render a second title right below this one, a leftover from when
                it was a scroll section. DEV-80 then dropped this block's own "Welcome
                back" eyebrow label, so the h1 leads — that eyebrow style has since been
                removed app-wide, so there is nothing to add back here.
                A bookmark for an unknown careerId has no title to show, so fall back to
                the generic heading rather than rendering a bare " Path". */}
            <div className="mt-8 max-w-xl">
              <h1 className="font-display font-bold text-h1 text-navy tracking-tight text-balance">
                {career ? `${career.title} Path` : 'Your Learning Roadmap'}
              </h1>
              <p className="font-body text-body text-navy/65 leading-snug mt-3">
                {locked
                  ? 'Roadmaps open for the careers your assessment matches you to.'
                  : 'Your matched path, progress, and skill gaps. Click any skill node for resources.'}
              </p>
            </div>
          </div>
        </div>

        {!resolved ? (
          <div className="flex justify-center py-24" role="status" aria-label="Loading your roadmap">
            <div className="h-8 w-8 rounded-full border-2 border-gold/30 border-t-gold animate-spin" />
          </div>
        ) : locked ? (
          <LockedPanel
            signedIn={!!user}
            onSignIn={() => setAuthModalOpen(true)}
            onStartAssessment={onStartAssessment}
          />
        ) : (
          // Key on the resolved skill set so a late-resolving gap set (this page's
          // history request, then the app's parallel restore) remounts rather than
          // half-applies: the gaps drive node status and the drawer hint, and the
          // roadmap's own fetch effect keys on the career alone.
          <Roadmap
            key={`${careerId}|${resolved.missing.join(',')}|${resolved.matched.join(',')}`}
            selectedCareer={careerId}
            missingSkills={resolved.missing}
            matchedSkills={resolved.matched}
          />
        )}
      </main>
      <Footer onReset={goHome} onStartAssessment={onStartAssessment} />
    </div>
  )
}

// DEV-82: what a locked roadmap shows instead of the canvas. The hero and "Back to
// home" stay above it, so the URL survives and the visitor always has a way out.
// Two doors, because a locked roadmap has two causes and they need different
// actions: signed out -> the auth modal; signed in but never recommended this
// career -> the assessment.
//
// The border is an inline color-mix, not `border-navy/10`: the theme tokens are
// plain CSS-var strings with no <alpha-value>, so an opacity modifier on them
// compiles to nothing at all and the border would fall back to preflight grey
// (frontend/CLAUDE.md). Same reason the copy is `text-navy opacity-65` — safe
// here because the element holds nothing but text. `bg-white/50` is fine: white
// is a hex default, not a token.
const PANEL_BORDER = 'color-mix(in srgb, var(--color-navy) 12%, transparent)'

function LockedPanel({ signedIn, onSignIn, onStartAssessment }) {
  return (
    <div className="max-w-7xl mx-auto px-6 py-20">
      <div
        className="mx-auto max-w-lg rounded-card border bg-white/50 px-8 py-14 text-center backdrop-blur-sm"
        style={{ borderColor: PANEL_BORDER }}
      >
        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full bg-gold opacity-90">
          <Lock size={24} className="text-navy" aria-hidden="true" />
        </div>
        <h2 className="font-display font-bold text-h2 text-navy tracking-tight">
          This roadmap is locked
        </h2>
        <p className="font-body text-body text-navy opacity-65 leading-snug mt-3 mb-8">
          {signedIn
            ? 'Your assessments haven’t matched you to this career yet. Take the assessment to see the paths that fit you.'
            : 'Sign in to take the assessment and open the roadmaps it matches you to.'}
        </p>
        <Button variant="primary" size="lg" onClick={signedIn ? onStartAssessment : onSignIn}>
          {signedIn ? 'Take the Assessment' : 'Sign In'}
        </Button>
      </div>
    </div>
  )
}
