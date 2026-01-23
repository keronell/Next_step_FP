import { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import Questionnaire from './pages/Questionnaire'
import Results from './pages/Results'
import Roadmap from './pages/Roadmap'
import Progress from './pages/Progress'

function App() {
  const [sessionId, setSessionId] = useState(localStorage.getItem('sessionId'))

  return (
    <Router>
      <Routes>
        <Route path="/" element={<Landing setSessionId={setSessionId} />} />
        <Route path="/questionnaire" element={<Questionnaire sessionId={sessionId} />} />
        <Route path="/results" element={<Results sessionId={sessionId} />} />
        <Route path="/roadmap" element={<Roadmap sessionId={sessionId} />} />
        <Route path="/progress" element={<Progress sessionId={sessionId} />} />
      </Routes>
    </Router>
  )
}

export default App

