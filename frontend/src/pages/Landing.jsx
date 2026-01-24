import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import './Landing.css'

function Landing({ setSessionId }) {
  const navigate = useNavigate()

  const handleStart = async () => {
    try {
      const response = await axios.post('/api/sessions')
      const sessionId = response.data.session_id
      setSessionId(sessionId)
      localStorage.setItem('sessionId', sessionId)
      navigate('/questionnaire')
    } catch (error) {
      console.error('Failed to start session:', error)
      alert('Failed to start session. Please try again.')
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
        <button className="start-button" onClick={handleStart}>
          <span>Start Assessment</span>
        </button>
        </div>
      </div>
      
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

