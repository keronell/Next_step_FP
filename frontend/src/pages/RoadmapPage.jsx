// DEV-76 / DEV-65: standalone, deep-linkable "Your Learning Roadmap" page at
// `/roadmap/{careerId}` — the returning-user home. It renders the roadmap
// (header/footer chrome around it), deliberately bypassing the Hero, "How It
// Works", Assessment and Results sections that the scroll app (App.jsx) stacks
// above the roadmap. A returning user with a completed assessment lands here
// directly; a bare bookmark still shows the generic roadmap.
//
// The roadmap itself is the existing <Roadmap> component, reused unchanged (it
// fetches its own roadmap data + progress). This page resolves the assessment-derived
// skill gaps for `careerId` so the roadmap can highlight them — preferring the
// recommendation the app already holds (the result the user just clicked), and only
// falling back to history/localStorage for true deep links.
import { useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import Header from '../components/Header'
import Footer from '../components/Footer'
import ParticleField from '../components/ParticleField'
import AuthModal from './AuthModal'
import Roadmap from './Roadmap'
import { CAREERS } from '../data'
import { fetchMySubmissions } from '../api'
import { useAuth } from '../contexts/AuthContext'
import { navigate } from '../hooks/useRoute'

// The recommendation entry for a given career within a recommendations array.
function findRec(recs, careerId) {
  return (recs || []).find((r) => r.id === careerId) || null
}

export default function RoadmapPage({ careerId, recommendations, profile, onStartAssessment, onLoadResults }) {
  const { user, authLoading } = useAuth()
  // `profile` rides with the gaps: /api/roadmap/{id} personalizes its LLM prompt
  // from it (DEV-60), and it must be the profile that produced THIS recommendation.
  const [skills, setSkills] = useState({ missing: [], matched: [], profile: null })
  const [resolving, setResolving] = useState(true)
  const [authModalOpen, setAuthModalOpen] = useState(false)

  // Resolve the skill gaps for this career. Prefer the recommendation the app
  // already holds (passed in when the user clicks "View Roadmap" right after a
  // submit) — at that moment the submission hasn't necessarily been persisted /
  // its selection applied yet, so re-fetching history could miss it or return a
  // stale pick. For a true deep link/bookmark (no app state) fall back to server
  // history when logged in, or localStorage when anonymous. No match anywhere →
  // render unpersonalized; the roadmap still loads from the backend / ROADMAPS.
  useEffect(() => {
    if (authLoading) return // wait for auth to settle before choosing a source
    let cancelled = false
    setResolving(true)

    const apply = (rec, profileSnapshot = null) => {
      if (cancelled) return
      setSkills({
        missing: rec?.missing_skills ?? [],
        matched: rec?.matched_skills ?? [],
        profile: profileSnapshot,
      })
      setResolving(false)
    }

    const passed = findRec(recommendations, careerId)
    if (passed) {
      apply(passed, profile ?? null)
      return () => { cancelled = true }
    }

    if (user) {
      fetchMySubmissions()
        .then((subs) => {
          // Most recent submission that includes this career; prefer the one the
          // user actually selected, matching App.jsx's restore-latest behavior.
          const sorted = [...(subs || [])].sort(
            (a, b) => new Date(b.created_at) - new Date(a.created_at),
          )
          const sub =
            sorted.find((s) => s.selected_career === careerId && findRec(s.recommendations, careerId)) ||
            sorted.find((s) => findRec(s.recommendations, careerId))
          // The snapshot stored with that submission, so the roadmap is personalized
          // by the profile it was scored with rather than the current run's.
          apply(sub ? findRec(sub.recommendations, careerId) : null, sub?.profile ?? null)
        })
        .catch(() => apply(null))
    } else {
      let recs = null
      try { recs = JSON.parse(localStorage.getItem('nextstep_last_recommendations')) } catch {} // eslint-disable-line no-empty
      // Anonymous: no profile snapshot is mirrored to localStorage, so none to apply.
      apply(findRec(recs, careerId))
    }

    return () => { cancelled = true }
  }, [careerId, user, authLoading, recommendations, profile])

  // NB: we deliberately do NOT record a career selection on mount here. selectCareer
  // is scoped to the anonymous session id (which survives sign-out), so recording on
  // a mere bookmark visit could overwrite a previous signed-in user's selected_career
  // on a shared browser. Selection is recorded only from the explicit "View Roadmap"
  // click (App.jsx::handleSelectCareer).

  const career = CAREERS.find((c) => c.id === careerId)

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
                back" label, so the h1 leads (hence no Eyebrow import in this file).
                A bookmark for an unknown careerId has no title to show, so fall back to
                the generic heading rather than rendering a bare " Path". */}
            <div className="mt-8 max-w-xl">
              <h1 className="font-display font-bold text-h1 text-navy tracking-tight text-balance">
                {career ? `${career.title} Path` : 'Your Learning Roadmap'}
              </h1>
              <p className="font-body text-body text-navy/65 leading-snug mt-3">
                Your matched path, progress, and skill gaps. Click any skill node for resources.
              </p>
            </div>
          </div>
        </div>

        {resolving ? (
          <div className="flex justify-center py-24" role="status" aria-label="Loading your roadmap">
            <div className="h-8 w-8 rounded-full border-2 border-gold/30 border-t-gold animate-spin" />
          </div>
        ) : (
          // Key on the resolved skill set: Roadmap fetches personalized roadmap
          // data from missingSkills but its fetch effect depends only on
          // selectedCareer, so if the gaps change after mount (e.g. this page's
          // history request resolves them, then the app's parallel restore resolves
          // a different set) it would highlight the new gaps over content generated
          // for the old ones. Remounting refetches so the two stay consistent.
          <Roadmap
            key={`${careerId}|${skills.missing.join(',')}|${skills.matched.join(',')}`}
            selectedCareer={careerId}
            missingSkills={skills.missing}
            matchedSkills={skills.matched}
            profile={skills.profile}
          />
        )}
      </main>
      <Footer onReset={goHome} onStartAssessment={onStartAssessment} />
    </div>
  )
}
