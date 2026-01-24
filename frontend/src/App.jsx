import { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import Questionnaire from './pages/Questionnaire'
import Results from './pages/Results'
import Roadmap from './pages/Roadmap'
import Progress from './pages/Progress'
import Header from './components/Header'
import Footer from './components/Footer'
import './App.css'

function App() {
  const [sessionId, setSessionId] = useState(localStorage.getItem('sessionId'))

  return (
    <Router>
      <div className="app-wrapper">
        <Header />
        <Routes>
          <Route path="/" element={<Landing setSessionId={setSessionId} />} />
          <Route path="/questionnaire" element={<Questionnaire sessionId={sessionId} />} />
          <Route path="/results" element={<Results sessionId={sessionId} />} />
          <Route path="/roadmap" element={<Roadmap sessionId={sessionId} />} />
          <Route path="/progress" element={<Progress sessionId={sessionId} />} />
        </Routes>
        <Footer />
      </div>
    </Router>
  )
}

export default App

