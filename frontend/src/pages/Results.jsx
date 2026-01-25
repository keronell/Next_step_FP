import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useToast } from '../components/ToastContainer'
import { ResultsSkeleton } from '../components/LoadingSkeleton'
import './Results.css'

function Results({ sessionId }) {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedRole, setSelectedRole] = useState(null)
  const [comparisonMode, setComparisonMode] = useState(false)
  const [selectedForComparison, setSelectedForComparison] = useState([])

  useEffect(() => {
    if (!sessionId) {
      navigate('/')
      return
    }

    // Check if this is adaptive quiz results
    const adaptiveResults = sessionStorage.getItem('adaptiveResults')
    if (adaptiveResults) {
      try {
        const data = JSON.parse(adaptiveResults)
        // Convert adaptive format to standard format
        setResults({
          top_roles: data.top_5_jobs.map(job => ({
            ...job,
            score: job.match_score || 0
          })),
          questions_answered: data.questions_answered
        })
        sessionStorage.removeItem('adaptiveResults')
        setLoading(false)
        return
      } catch (e) {
        console.error('Failed to parse adaptive results:', e)
      }
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
      showToast('Failed to generate roadmap. Please try again.', 'error')
    }
  }

  const toggleComparison = (roleId) => {
    if (selectedForComparison.includes(roleId)) {
      setSelectedForComparison(selectedForComparison.filter(id => id !== roleId))
    } else {
      if (selectedForComparison.length < 3) {
        setSelectedForComparison([...selectedForComparison, roleId])
      } else {
        showToast('You can compare up to 3 roles at once', 'warning')
      }
    }
  }

  const toggleComparisonMode = () => {
    setComparisonMode(!comparisonMode)
    if (comparisonMode) {
      setSelectedForComparison([])
    }
  }

  const getSelectedRoles = () => {
    return results.top_roles.filter(role => selectedForComparison.includes(role.id))
  }

  if (loading) {
    return (
      <div className="results">
        <div className="results-hero-section">
          <div className="results-hero-image"></div>
          <div className="results-hero-overlay"></div>
        </div>
        <ResultsSkeleton />
      </div>
    )
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
        <div className="results-header-actions">
          <div>
            <h1>Your Career Matches</h1>
            <p className="results-subtitle">
              Based on your answers, here are the top 5 roles that match your profile:
            </p>
          </div>
          <button 
            className={`comparison-toggle ${comparisonMode ? 'active' : ''}`}
            onClick={toggleComparisonMode}
          >
            {comparisonMode ? '✓ Comparison Mode' : 'Compare Roles'}
          </button>
        </div>

        {comparisonMode && selectedForComparison.length > 0 && (
          <div className="comparison-view">
            <h2 className="comparison-title">Role Comparison</h2>
            <div className="comparison-grid">
              {getSelectedRoles().map(role => (
                <div key={role.id} className="comparison-card">
                  <h3>{role.name}</h3>
                  <div className="comparison-score">{role.score}% Match</div>
                  <p className="comparison-description">{role.description}</p>
                  {role.reasons && role.reasons.length > 0 && (
                    <div className="comparison-reasons">
                      <strong>Key Areas:</strong>
                      <ul>
                        {role.reasons.slice(0, 3).map((reason, idx) => (
                          <li key={idx}>{reason.message}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

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

              <div className="role-actions">
                {comparisonMode && (
                  <button
                    className={`compare-button ${selectedForComparison.includes(role.id) ? 'selected' : ''}`}
                    onClick={() => toggleComparison(role.id)}
                  >
                    {selectedForComparison.includes(role.id) ? '✓ Comparing' : '+ Compare'}
                  </button>
                )}
                <button
                  className={`select-role-button ${selectedRole === role.id ? 'selected' : ''}`}
                  onClick={() => handleSelectRole(role.id)}
                  disabled={selectedRole === role.id}
                >
                  <span>{selectedRole === role.id ? 'Generating Roadmap...' : 'Select This Role'}</span>
                </button>
              </div>
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

