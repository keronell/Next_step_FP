import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import './Results.css'

function Results({ sessionId }) {
  const navigate = useNavigate()
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedRole, setSelectedRole] = useState(null)

  useEffect(() => {
    if (!sessionId) {
      navigate('/')
      return
    }

    // Fetch results (they should already be computed)
    axios.post(`/api/sessions/${sessionId}/compute`)
      .then(response => {
        setResults(response.data)
        setLoading(false)
      })
      .catch(error => {
        console.error('Failed to load results:', error)
        setLoading(false)
      })
  }, [sessionId, navigate])

  const handleSelectRole = async (roleId) => {
    setSelectedRole(roleId)
    try {
      await axios.post(`/api/sessions/${sessionId}/roadmap`, { role_id: roleId })
      navigate('/roadmap')
    } catch (error) {
      console.error('Failed to generate roadmap:', error)
      alert('Failed to generate roadmap. Please try again.')
    }
  }

  if (loading) {
    return <div className="results-loading">Computing your results...</div>
  }

  if (!results) {
    return <div className="results-error">No results available</div>
  }

  return (
    <div className="results">
      <div className="results-hero-section">
        <div className="results-hero-image"></div>
        <div className="results-hero-overlay"></div>
      </div>
      <div className="results-container">
        <h1>Your Career Matches</h1>
        <p className="results-subtitle">
          Based on your answers, here are the top 5 roles that match your profile:
        </p>

        <div className="roles-grid">
          {results.top_roles.map((role, index) => (
            <div key={role.id} className="role-card">
              <div className="role-header">
                <div className="role-rank">#{index + 1}</div>
                <div className="role-score">{role.score}% Match</div>
              </div>
              <h2 className="role-name">{role.name}</h2>
              <p className="role-description">{role.description}</p>
              
              {role.reasons && role.reasons.length > 0 && (
                <div className="role-gaps">
                  <div className="gaps-title">Key areas to improve:</div>
                  <ul className="gaps-list">
                    {role.reasons.map((reason, idx) => (
                      <li key={idx}>{reason.message}</li>
                    ))}
                  </ul>
                </div>
              )}

              <button
                className={`select-role-button ${selectedRole === role.id ? 'selected' : ''}`}
                onClick={() => handleSelectRole(role.id)}
                disabled={selectedRole === role.id}
              >
                <span>{selectedRole === role.id ? 'Generating Roadmap...' : 'Select This Role'}</span>
              </button>
            </div>
          ))}
        </div>

        <div className="results-footer">
          <p>Select a role above to generate your personalized learning roadmap</p>
        </div>
      </div>
    </div>
  )
}

export default Results

