import { useEffect, useRef, useState } from 'react'
import Header from './components/Header'
import Footer from './components/Footer'
import Hero from './pages/Landing'
import HowItWorks from './pages/HowItWorks'
import Assessment from './pages/Questionnaire'
import Results from './pages/Results'
import Roadmap from './pages/Roadmap'
import History from './pages/History'
import AuthModal from './pages/AuthModal'
import { computeResults } from './data'
import { submitQuestionnaire, selectCareer, fetchMySubmissions } from './api'
import { useAuth } from './contexts/AuthContext'

function App() {
  const { user, authLoading } = useAuth()

  const [phase, setPhase] = useState('idle')
  const [results, setResults] = useState(null)
  const [notice, setNotice] = useState(null)
  const [selectedCareer, setSelectedCareer] = useState(null)
  const [activeTooltip, setActiveTooltip] = useState(null)
  const [authModalOpen, setAuthModalOpen] = useState(false)

  const assessmentRef = useRef(null)
  const resultsRef = useRef(null)
  const roadmapRef = useRef(null)
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
  useEffect(() => {
    if (user) return
    if (phase === 'results_ready' && results) {
      localStorage.setItem('nextstep_last_recommendations', JSON.stringify(results))
      localStorage.setItem('nextstep_last_career', selectedCareer || '')
    } else if (phase === 'idle') {
      localStorage.removeItem('nextstep_last_recommendations')
      localStorage.removeItem('nextstep_last_career')
    }
  }, [phase, results, selectedCareer, user])

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
      setNotice(recs.length === 0 ? 'empty' : null)
    } catch (err) {
      console.warn('Falling back to local results:', err)
      setResults(computeResults(answers))
      setNotice('offline')
    }
    setPhase('results_ready')
    scrollTo(resultsRef)
  }

  const handleSelectCareer = (careerId) => {
    setSelectedCareer(careerId)
    setActiveTooltip(null)
    selectCareer(careerId)
    scrollTo(roadmapRef)
  }

  const handleLoadHistory = (recommendations, careerId = null) => {
    setResults(recommendations)
    setNotice(null)
    setSelectedCareer(careerId)
    setActiveTooltip(null)
    setPhase('results_ready')
    scrollTo(resultsRef)
  }

  const handleReset = () => {
    setPhase('idle')
    setResults(null)
    setNotice(null)
    setSelectedCareer(null)
    setActiveTooltip(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="min-h-screen bg-cream">
      <Header phase={phase} onReset={handleReset} onOpenAuth={() => setAuthModalOpen(true)} />
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
        <div ref={roadmapRef}>
          <Roadmap
            selectedCareer={selectedCareer}
            missingSkills={results?.find((r) => r.id === selectedCareer)?.missing_skills ?? []}
            activeTooltip={activeTooltip}
            setActiveTooltip={setActiveTooltip}
          />
        </div>
        <div ref={historyRef}>
          <History user={user} onLoadResults={handleLoadHistory} />
        </div>
      </main>
      <Footer onReset={handleReset} />
    </div>
  )
}

export default App
