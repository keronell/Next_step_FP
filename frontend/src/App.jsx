import { useRef, useState } from 'react'
import Header from './components/Header'
import Footer from './components/Footer'
import Hero from './pages/Landing'
import HowItWorks from './pages/HowItWorks'
import Assessment from './pages/Questionnaire'
import Results from './pages/Results'
import Roadmap from './pages/Roadmap'
import History from './pages/History'
import { computeResults } from './data'
import { submitQuestionnaire, selectCareer } from './api'
import { useAuth } from './contexts/AuthContext'

function App() {
  const { user } = useAuth()

  const [phase, setPhase] = useState('idle')
  const [results, setResults] = useState(null)
  const [notice, setNotice] = useState(null)
  const [selectedCareer, setSelectedCareer] = useState(null)
  const [activeTooltip, setActiveTooltip] = useState(null)

  const assessmentRef = useRef(null)
  const resultsRef = useRef(null)
  const roadmapRef = useRef(null)
  const historyRef = useRef(null)

  const scrollTo = (ref) => {
    setTimeout(() => ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
  }

  const handleStart = () => {
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

  const handleLoadHistory = (recommendations) => {
    setResults(recommendations)
    setNotice(null)
    setSelectedCareer(null)
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
      <Header phase={phase} onReset={handleReset} />
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
