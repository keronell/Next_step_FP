import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import axios from 'axios'
import './Progress.css'

function Progress({ sessionId }) {
  const navigate = useNavigate()
  const [roadmap, setRoadmap] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!sessionId) {
      navigate('/')
      return
    }

    axios.get(`/api/sessions/${sessionId}/roadmap`)
      .then(response => {
        setRoadmap(response.data)
        setLoading(false)
      })
      .catch(error => {
        console.error('Failed to load progress:', error)
        setLoading(false)
      })
  }, [sessionId, navigate])

  const handleToggleStep = async (itemId, currentStatus) => {
    const newStatus = currentStatus === 'completed' ? 'pending' : 'completed'
    
    try {
      await axios.patch(`/api/roadmap-items/${itemId}`, { status: newStatus })
      
      const response = await axios.get(`/api/sessions/${sessionId}/roadmap`)
      setRoadmap(response.data)
    } catch (error) {
      console.error('Failed to update step:', error)
    }
  }

  if (loading) {
    return <div className="progress-loading">Loading your progress...</div>
  }

  if (!roadmap) {
    return (
      <div className="progress-error">
        <p>No roadmap found. Please select a role first.</p>
        <Link to="/results">Go to Results</Link>
      </div>
    )
  }

  const completedCount = roadmap.items.filter(item => item.status === 'completed').length
  const totalCount = roadmap.items.length

  return (
    <div className="progress">
      <div className="progress-container">
        <div className="progress-header">
          <h1>Your Progress</h1>
          <div className="progress-summary">
            <div className="summary-card">
              <div className="summary-number">{completedCount}</div>
              <div className="summary-label">Completed Steps</div>
            </div>
            <div className="summary-card">
              <div className="summary-number">{totalCount - completedCount}</div>
              <div className="summary-label">Remaining Steps</div>
            </div>
            <div className="summary-card highlight">
              <div className="summary-number">{roadmap.progress}%</div>
              <div className="summary-label">Overall Progress</div>
            </div>
          </div>
        </div>

        <div className="progress-steps">
          {roadmap.items.map((item, index) => (
            <div key={item.id} className={`progress-step ${item.status === 'completed' ? 'completed' : ''}`}>
              <div className="step-checkbox">
                <input
                  type="checkbox"
                  checked={item.status === 'completed'}
                  onChange={() => handleToggleStep(item.id, item.status)}
                />
              </div>
              <div className="step-info">
                <div className="step-title-row">
                  <h3>{item.title}</h3>
                  <span className="step-status">
                    {item.status === 'completed' ? '✓ Completed' : 'Pending'}
                  </span>
                </div>
                <p className="step-description">{item.description}</p>
                {item.completed_at && (
                  <div className="step-completed-date">
                    Completed on {new Date(item.completed_at).toLocaleDateString()}
                  </div>
                )}
                {item.resources && item.resources.length > 0 && (
                  <div className="step-resources-count">
                    {item.resources.length} resource{item.resources.length > 1 ? 's' : ''} available
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="progress-footer">
          <Link to="/roadmap" className="back-to-roadmap-link">
            ← Back to Roadmap
          </Link>
        </div>
      </div>
    </div>
  )
}

export default Progress

