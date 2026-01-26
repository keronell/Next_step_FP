import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useToast } from '../components/ToastContainer'
import './Landing.css'

function Landing({ setSessionId }) {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [showModal, setShowModal] = useState(false)
  const [isStarting, setIsStarting] = useState(false)

  const handleStartClick = () => {
    setShowModal(true)
  }

  const handleCloseModal = () => {
    setShowModal(false)
  }

  const handleStart = async () => {
    setIsStarting(true)
    try {
      const response = await axios.post('/api/sessions')
      const sessionId = response.data.session_id
      setSessionId(sessionId)
      localStorage.setItem('sessionId', sessionId)
      showToast('Assessment started! Good luck!', 'success')
      navigate('/questionnaire')
    } catch (error) {
      console.error('Failed to start session:', error)
      showToast('Failed to start session. Please try again.', 'error')
      setIsStarting(false)
    }
  }

  return (
    <div className="landing">
      <div className="landing-hero-image">
        <div className="hero-image-overlay"></div>
      </div>
      <div className="landing-main-wrapper">
        <div className="landing-content">
        <h1>NextStep Career Matcher</h1>
        <p className="subtitle">
          Discover your ideal tech career path through a personalized assessment
        </p>
        <p className="description">
          Answer 10 questions about your skills, interests, and work style to get matched
          with the top 5 tech roles that fit you best, plus a personalized learning roadmap.
        </p>
        <button className="start-button" onClick={handleStartClick}>
          <span>Start Assessment</span>
        </button>
        </div>
      </div>
      
      {showModal && (
        <div className="landing-modal-overlay" onClick={handleCloseModal}>
          <div className="landing-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={handleCloseModal}>×</button>
            <div className="modal-content">
              <h2>Ready to Start?</h2>
              <p>You're about to begin a 10-question assessment that will help us match you with the best tech career roles.</p>
              <div className="modal-info">
                <div className="modal-info-item">
                  <span className="modal-icon">⏱️</span>
                  <span>Takes about 5-10 minutes</span>
                </div>
                <div className="modal-info-item">
                  <span className="modal-icon">📝</span>
                  <span>10 questions total</span>
                </div>
                <div className="modal-info-item">
                  <span className="modal-icon">🎯</span>
                  <span>Get matched with top 5 roles</span>
                </div>
              </div>
              <div className="modal-actions">
                <button className="modal-button secondary" onClick={handleCloseModal} disabled={isStarting}>
                  Cancel
                </button>
                <button className="modal-button primary" onClick={handleStart} disabled={isStarting}>
                  {isStarting ? 'Starting...' : 'Start Assessment'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      
      <div className="landing-features">
        <div className="feature-item">
          <div className="feature-icon target-roles"></div>
          <h3>Target Roles</h3>
          <p>Discover roles that match your skills</p>
        </div>
        <div className="feature-item">
          <div className="feature-icon learning-pathways"></div>
          <h3>Learning Pathways</h3>
          <p>Personalized learning journeys</p>
        </div>
        <div className="feature-item">
          <div className="feature-icon technologies"></div>
          <h3>Technologies</h3>
          <p>Master the right tech stack</p>
        </div>
        <div className="feature-item">
          <div className="feature-icon career-roadmap"></div>
          <h3>Career Roadmap</h3>
          <p>Step-by-step career guidance</p>
        </div>
      </div>
    </div>
  )
}

export default Landing

