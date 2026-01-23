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
  )
}

export default Landing

