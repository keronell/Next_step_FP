import { useState, useRef } from 'react'
import Header from './components/Header'
import Footer from './components/Footer'
import Hero from './pages/Landing'
import HowItWorks from './pages/HowItWorks'
import Assessment from './pages/Questionnaire'
import Results from './pages/Results'
import Roadmap from './pages/Roadmap'
import { computeResults } from './data'

function App() {
  const [phase, setPhase] = useState('idle')
  const [results, setResults] = useState(null)
  const [selectedCareer, setSelectedCareer] = useState(null)
  const [activeTooltip, setActiveTooltip] = useState(null)

  const assessmentRef = useRef(null)
  const resultsRef = useRef(null)
  const roadmapRef = useRef(null)

  const scrollTo = (ref) => {
    setTimeout(() => ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
  }

  const handleStart = () => {
    setPhase('assessing')
    scrollTo(assessmentRef)
  }

  const handleQuizComplete = (answers) => {
    setPhase('loading')
    setTimeout(() => {
      const top3 = computeResults(answers)
      setResults(top3)
      setPhase('results_ready')
      scrollTo(resultsRef)
    }, 2600)
  }

  const handleSelectCareer = (careerId) => {
    setSelectedCareer(careerId)
    setActiveTooltip(null)
    scrollTo(roadmapRef)
  }

  const handleReset = () => {
    setPhase('idle')
    setResults(null)
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
            onSelectCareer={handleSelectCareer}
            selectedCareer={selectedCareer}
          />
        </div>
        <div ref={roadmapRef}>
          <Roadmap
            selectedCareer={selectedCareer}
            activeTooltip={activeTooltip}
            setActiveTooltip={setActiveTooltip}
          />
        </div>
      </main>
      <Footer onReset={handleReset} />
    </div>
  )
}

export default App
