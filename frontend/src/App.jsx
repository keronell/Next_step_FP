import { useEffect, useRef, useState } from 'react'
import Header from './components/Header'
import Footer from './components/Footer'
import Hero from './pages/Landing'
import HowItWorks from './pages/HowItWorks'
import Assessment from './pages/Questionnaire'
import Results from './pages/Results'
import History from './pages/History'
import AuthModal from './pages/AuthModal'
import RoadmapPage from './pages/RoadmapPage'
import { computeResults } from './data'
import { submitQuestionnaire, selectCareer, fetchMySubmissions } from './api'
import { useAuth } from './contexts/AuthContext'
import { useRoute, matchRoadmap, navigate, navigateToSection, consumePendingScroll } from './hooks/useRoute'

function App() {
  const { user, authLoading } = useAuth()

  // Deep-link routing: `/roadmap/{id}` renders the standalone roadmap (bypassing
  // the intro/questionnaire); every other path renders the scroll app below.
  const path = useRoute()
  const roadmapCareerId = matchRoadmap(path)

  const [phase, setPhase] = useState('idle')
  const [results, setResults] = useState(null)
  const [notice, setNotice] = useState(null)
  const [selectedCareer, setSelectedCareer] = useState(null)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  // The career whose roadmap a returning user can jump straight to (their most
  // recent completed assessment). Drives the header's "My Roadmap" shortcut; null
  // for users with no completed assessment, so their flow stays untouched.
  const [resumeCareerId, setResumeCareerId] = useState(null)

  const assessmentRef = useRef(null)
  const resultsRef = useRef(null)
  const historyRef = useRef(null)

  const scrollTo = (ref) => {
    setTimeout(() => ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
  }

  // Restore the last results view on refresh. Runs once auth resolves; only acts
  // while idle so we never clobber an active flow. handleLoadHistory is omitted
  // from the deps on purpose (it's a new fn each render).
  useEffect(() => {
    if (authLoading || phase !== 'idle') return
    if (user) {
      fetchMySubmissions()
        .then((subs) => {
          if (!subs?.length) return
          const latest = [...subs].sort(
            (a, b) => new Date(b.created_at) - new Date(a.created_at),
          )[0]
          handleLoadHistory(latest.recommendations, latest.selected_career ?? null)
        })
        .catch(() => {})
    } else {
      let recs = null
      try { recs = JSON.parse(localStorage.getItem('nextstep_last_recommendations')) } catch {} // eslint-disable-line no-empty
      if (recs?.length) handleLoadHistory(recs, localStorage.getItem('nextstep_last_career') || null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, user])

  // Mirror anonymous users' last results to localStorage so a refresh can restore
  // them. Logged-in users use server history, so we never write their data here.
  // Waits for authLoading like the restore effect above - otherwise the initial
  // idle render clears the keys before the restore effect gets to read them.
  const prevUserRef = useRef(user)
  useEffect(() => {
    // On sign-out (truthy user -> null), clear the anonymous restore keys AND
    // drop the signed-out user's results view. Skipping the write on just this
    // render isn't enough: their results/phase linger in state, so a later
    // dependency change (e.g. selecting a different roadmap) would re-run this
    // effect with user === null and phase === 'results_ready' and mirror that
    // prior user's data as anonymous. Resetting the view removes that path.
    if (prevUserRef.current && !user) {
      prevUserRef.current = user
      localStorage.removeItem('nextstep_last_recommendations')
      localStorage.removeItem('nextstep_last_career')
      setPhase('idle')
      setResults(null)
      setNotice(null)
      setSelectedCareer(null)
      setResumeCareerId(null)
      return
    }
    prevUserRef.current = user

    if (user || authLoading) return
    if (phase === 'results_ready' && results) {
      localStorage.setItem('nextstep_last_recommendations', JSON.stringify(results))
      localStorage.setItem('nextstep_last_career', selectedCareer || '')
    } else if (phase === 'idle') {
      localStorage.removeItem('nextstep_last_recommendations')
      localStorage.removeItem('nextstep_last_career')
    }
  }, [phase, results, selectedCareer, user, authLoading])

  // Returning to the scroll app from a route (e.g. the roadmap page) may carry a
  // deferred section target: a nav control clicked while its section wasn't mounted
  // (see navigateToSection). Honor it once we're back on the scroll app, giving the
  // sections a tick to mount/lay out before scrolling.
  useEffect(() => {
    if (roadmapCareerId) return
    const id = consumePendingScroll()
    if (!id) return
    const t = setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 80)
    return () => clearTimeout(t)
  }, [roadmapCareerId])

  const handleStart = () => {
    if (authLoading) return
    if (!user) {
      setAuthModalOpen(true)
      return
    }
    setPhase('assessing')
    scrollTo(assessmentRef)
  }

  const handleQuizComplete = async (answers) => {
    if (phase === 'loading') return
    setPhase('loading')
    setNotice(null)
    try {
      const recs = await submitQuestionnaire(answers)
      setResults(recs)
      setResumeCareerId(recs?.[0]?.id ?? null)
      setNotice(recs.length === 0 ? 'empty' : null)
    } catch (err) {
      console.warn('Falling back to local results:', err)
      const local = computeResults(answers)
      setResults(local)
      setResumeCareerId(local?.[0]?.id ?? null)
      setNotice('offline')
    }
    setPhase('results_ready')
    scrollTo(resultsRef)
  }

  const handleSelectCareer = (careerId) => {
    // The roadmap lives on its own page now (no inline section on the front page):
    // open it there. Record the selection HERE, on the explicit result click —
    // not on the roadmap page's mount, so merely opening a bookmark can't record a
    // selection (which is session-scoped and could clobber another account's).
    // Set selectedCareer too (not just the resume id) so returning via the Back
    // button shows the card as selected, and the anonymous-persistence effect
    // mirrors the right nextstep_last_career for a later reload.
    setSelectedCareer(careerId)
    setResumeCareerId(careerId)
    selectCareer(careerId)
    navigate(`/roadmap/${encodeURIComponent(careerId)}`)
  }

  const handleLoadHistory = (recommendations, careerId = null) => {
    setResults(recommendations)
    setNotice(null)
    setSelectedCareer(careerId)
    // The "My Roadmap" shortcut points at the selected career, else the top match.
    setResumeCareerId(careerId ?? recommendations?.[0]?.id ?? null)
    setPhase('results_ready')
    scrollTo(resultsRef)
  }

  const handleReset = () => {
    setPhase('idle')
    setResults(null)
    setNotice(null)
    setSelectedCareer(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Header's Assessment / Start Assessment controls. Questionnaire renders nothing
  // while phase is 'results_ready', so a returning user (whose background restore
  // set that phase, e.g. while the standalone roadmap page was showing) would land
  // on a blank assessment section. Reset to the idle start card first — but never
  // disturb an in-progress assessment. navigateToSection scrolls here, or routes
  // home and defers the scroll when we're on the roadmap route.
  const handleGoToAssessment = () => {
    if (phase !== 'assessing' && phase !== 'loading') {
      setPhase('idle')
      setResults(null)
      setNotice(null)
      setSelectedCareer(null)
    }
    navigateToSection('assessment')
  }

  // Standalone roadmap route (DEV-76/DEV-65): render only the roadmap, skipping
  // the whole intro/questionnaire flow the scroll app renders below. Hand the page
  // the current results so a just-clicked "View Roadmap" uses that recommendation
  // directly, rather than re-fetching a not-yet-persisted submission from history.
  if (roadmapCareerId) {
    return (
      <RoadmapPage
        careerId={roadmapCareerId}
        recommendations={results}
        onStartAssessment={handleGoToAssessment}
      />
    )
  }

  return (
    <div className="min-h-screen bg-cream">
      <Header
        phase={phase}
        onReset={handleReset}
        onOpenAuth={() => setAuthModalOpen(true)}
        onStartAssessment={handleGoToAssessment}
        roadmapCareerId={resumeCareerId}
      />
      <AuthModal open={authModalOpen} onClose={() => setAuthModalOpen(false)} />
      <main>
        <Hero onStart={handleStart} />
        <HowItWorks />
        <div ref={assessmentRef}>
          <Assessment
            phase={phase}
            onStart={handleStart}
            onComplete={handleQuizComplete}
          />
        </div>
        <div ref={resultsRef}>
          <Results
            phase={phase}
            results={results}
            notice={notice}
            onRetry={handleStart}
            onSelectCareer={handleSelectCareer}
            selectedCareer={selectedCareer}
          />
        </div>
        <div ref={historyRef}>
          <History user={user} onLoadResults={handleLoadHistory} />
        </div>
      </main>
      <Footer onReset={handleReset} onStartAssessment={handleGoToAssessment} />
    </div>
  )
}

export default App
