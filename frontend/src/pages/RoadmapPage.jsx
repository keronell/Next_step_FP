// DEV-76 / DEV-65: standalone, deep-linkable roadmap view at `/roadmap/{careerId}`.
// It renders ONLY the roadmap (plus header/footer chrome) — deliberately bypassing
// the Hero, "How It Works", Assessment and Results sections that the scroll app
// (App.jsx) stacks above the roadmap. A returning user with a completed assessment
// lands here directly; a bare bookmark still shows the generic roadmap.
//
// The roadmap itself is the existing <Roadmap> component, reused unchanged (it
// fetches its own roadmap data + progress). All this page adds is resolving the
// assessment-derived skill gaps for `careerId` so the roadmap can highlight them.
import { useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import Header from '../components/Header'
import Footer from '../components/Footer'
import Roadmap from './Roadmap'
import { fetchMySubmissions, selectCareer } from '../api'
import { useAuth } from '../contexts/AuthContext'
import { navigate } from '../hooks/useRoute'

// The recommendation entry for a given career within a recommendations array.
function findRec(recs, careerId) {
  return (recs || []).find((r) => r.id === careerId) || null
}

export default function RoadmapPage({ careerId }) {
  const { user, authLoading } = useAuth()
  const [skills, setSkills] = useState({ missing: [], matched: [] })
  const [resolving, setResolving] = useState(true)

  // Resolve the skill gaps for this career from the user's completed assessment:
  // server history when logged in, localStorage when anonymous. No match (e.g. a
  // bare bookmark, or a career they never assessed) → render unpersonalized; the
  // roadmap still loads from the backend / ROADMAPS fallback.
  useEffect(() => {
    if (authLoading) return // wait for auth to settle before choosing a source
    let cancelled = false
    setResolving(true)

    const apply = (rec) => {
      if (cancelled) return
      setSkills({ missing: rec?.missing_skills ?? [], matched: rec?.matched_skills ?? [] })
      setResolving(false)
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
          apply(sub ? findRec(sub.recommendations, careerId) : null)
        })
        .catch(() => apply(null))
    } else {
      let recs = null
      try { recs = JSON.parse(localStorage.getItem('nextstep_last_recommendations')) } catch {} // eslint-disable-line no-empty
      apply(findRec(recs, careerId))
    }

    return () => { cancelled = true }
  }, [careerId, user, authLoading])

  // Record the deep-linked choice, mirroring App.jsx::handleSelectCareer.
  useEffect(() => { selectCareer(careerId) }, [careerId])

  const goHome = () => navigate('/')

  return (
    <div className="min-h-screen bg-cream">
      <Header phase="idle" onReset={goHome} onOpenAuth={goHome} roadmapCareerId={careerId} />
      <main>
        <div className="max-w-7xl mx-auto px-6 pt-24 pb-0">
          <button
            onClick={goHome}
            className="focus-ring inline-flex items-center gap-1.5 px-4 py-2 rounded-xl font-body text-small font-medium text-navy/65 hover:text-navy hover:bg-navy/[0.04] transition-all duration-fast"
          >
            <ArrowLeft size={15} aria-hidden="true" />
            Back to home
          </button>
        </div>

        {resolving ? (
          <div className="flex justify-center py-24" role="status" aria-label="Loading your roadmap">
            <div className="h-8 w-8 rounded-full border-2 border-gold/30 border-t-gold animate-spin" />
          </div>
        ) : (
          <Roadmap
            selectedCareer={careerId}
            missingSkills={skills.missing}
            matchedSkills={skills.matched}
          />
        )}
      </main>
      <Footer onReset={goHome} />
    </div>
  )
}
