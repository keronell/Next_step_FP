import { useState, useEffect, useRef } from 'react'
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
  const adaptiveResultsProcessed = useRef(false)

  // Debug: log when results change
  useEffect(() => {
    if (results) {
      console.log('Results state updated:', results)
      console.log('Top roles:', results.top_roles)
      if (results.top_roles && results.top_roles.length > 0) {
        console.log('First role in state:', results.top_roles[0])
        console.log('First role score in state:', results.top_roles[0].score)
      }
    }
  }, [results])

  useEffect(() => {
    if (!sessionId) {
      navigate('/')
      return
    }

    // Prevent processing if we've already handled adaptive results
    if (adaptiveResultsProcessed.current) {
      console.log('Adaptive results already processed, skipping')
      return
    }

    // Check if this is adaptive quiz results
    const adaptiveResults = sessionStorage.getItem('adaptiveResults')
    if (adaptiveResults) {
      try {
        adaptiveResultsProcessed.current = true // Mark as processed
        const data = JSON.parse(adaptiveResults)
        console.log('Adaptive results data:', data)
        console.log('Top 5 jobs:', data.top_5_jobs)
        
        // Convert adaptive format to standard format
        const topRoles = data.top_5_jobs.map(job => {
          console.log('Processing job:', job.id, 'match_score:', job.match_score, 'type:', typeof job.match_score)
          // Ensure match_score is converted to number and used as score
          const score = typeof job.match_score === 'number' ? job.match_score : 
                       typeof job.match_score === 'string' ? parseFloat(job.match_score) : 0
          console.log('Final score for', job.id, ':', score)
          return {
            ...job,
            score: score,
            // Adaptive quiz doesn't have reasons, so don't show skill gaps
            reasons: []
          }
        })
        
        console.log('Final top_roles:', topRoles)
        console.log('First role score:', topRoles[0]?.score, 'match_score:', topRoles[0]?.match_score)
        
        const resultsData = {
          top_roles: topRoles,
          questions_answered: data.questions_answered
        }
        
        console.log('Setting results:', resultsData)
        // Remove from sessionStorage IMMEDIATELY to prevent re-triggering
        sessionStorage.removeItem('adaptiveResults')
        setResults(resultsData)
        setLoading(false)
        // IMPORTANT: Return early to prevent standard quiz computation
        return
      } catch (e) {
        console.error('Failed to parse adaptive results:', e)
        // If parsing fails, remove the bad data and continue to standard quiz
        sessionStorage.removeItem('adaptiveResults')
        adaptiveResultsProcessed.current = false // Reset flag on error
      }
    }

    // Only fetch standard quiz results if we don't have adaptive results
    // This should only run for standard quiz, not adaptive
    console.log('Fetching standard quiz results for session:', sessionId)
    axios.post(`/api/sessions/${sessionId}/compute`)
      .then(response => {
        console.log('Standard quiz results received:', response.data)
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

  // Debug: log what we're about to render
  console.log('Rendering results:', results)
  console.log('First role in results:', results.top_roles?.[0])
  console.log('First role score:', results.top_roles?.[0]?.score)

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
              {getSelectedRoles().map(role => {
                const displayScore = role.score ?? role.match_score ?? 0
                return (
                <div key={role.id} className="comparison-card">
                  <h3>{role.name}</h3>
                  <div className="comparison-score">{displayScore}% Match</div>
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
                )
              })}
            </div>
          </div>
        )}

        <div className="roles-grid">
          {results.top_roles.map((role, index) => {
            // Debug each role being rendered
            console.log(`Rendering role ${index}:`, role.id, 'score:', role.score, 'match_score:', role.match_score, 'all keys:', Object.keys(role))
            const displayScore = role.score ?? role.match_score ?? 0
            console.log(`Display score for ${role.id}:`, displayScore)
            return (
            <div key={role.id} className="role-card">
              <div className="role-header">
                <div className="role-rank">#{index + 1}</div>
                <div className="role-score" data-score={displayScore}>{displayScore}% Match</div>
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
            )
          })}
        </div>

        <div className="results-footer">
          <p>Select a role above to generate your personalized learning roadmap</p>
        </div>
      </div>
    </div>
  )
}

export default Results

