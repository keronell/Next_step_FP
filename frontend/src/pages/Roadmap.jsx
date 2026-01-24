import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import axios from 'axios'
import './Roadmap.css'

function Roadmap({ sessionId }) {
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
        console.error('Failed to load roadmap:', error)
        setLoading(false)
      })
  }, [sessionId, navigate])

  const handleCompleteStep = async (itemId, currentStatus) => {
    const newStatus = currentStatus === 'completed' ? 'pending' : 'completed'
    
    try {
      await axios.patch(`/api/roadmap-items/${itemId}`, { status: newStatus })
      
      // Reload roadmap to get updated progress
      const response = await axios.get(`/api/sessions/${sessionId}/roadmap`)
      setRoadmap(response.data)
    } catch (error) {
      console.error('Failed to update step:', error)
    }
  }

  if (loading) {
    return <div className="roadmap-loading">Loading your roadmap...</div>
  }

  if (!roadmap) {
    return (
      <div className="roadmap-error">
        <p>No roadmap found. Please select a role first.</p>
        <Link to="/results">Go to Results</Link>
      </div>
    )
  }

  return (
    <div className="roadmap">
      <div className="roadmap-hero-bg"></div>
      <div className="roadmap-container">
        <div className="roadmap-header">
          <Link to="/results" className="roadmap-back-button">
            ← Back to Results
          </Link>
          <h1>Your Learning Roadmap</h1>
          <div className="roadmap-role">
            <h2>{roadmap.role_name}</h2>
            <p>{roadmap.role_description}</p>
          </div>
          <div className="progress-section">
            <div className="progress-label">Overall Progress</div>
            <div className="progress-bar-large">
              <div 
                className="progress-fill-large" 
                style={{ width: `${roadmap.progress}%` }}
              >
                {roadmap.progress > 5 ? `${roadmap.progress}%` : ''}
              </div>
              {roadmap.progress <= 5 && (
                <div className="progress-text-overlay">
                  {roadmap.progress}%
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="roadmap-steps">
          {roadmap.items.map((item, index) => (
            <div key={item.id} className={`roadmap-step ${item.status === 'completed' ? 'completed' : ''}`}>
              <div className="step-header">
                <div className="step-number">{item.step_number}</div>
                <div className="step-content">
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                </div>
                <button
                  className={`complete-button ${item.status === 'completed' ? 'completed' : ''}`}
                  onClick={() => handleCompleteStep(item.id, item.status)}
                >
                  <span>{item.status === 'completed' ? '✓ Completed' : 'Mark Complete'}</span>
                </button>
              </div>

              {item.resources && item.resources.length > 0 && (
                <div className="step-resources">
                  <div className="resources-title">Learning Resources:</div>
                  <div className="resources-list">
                    {item.resources.map((resource, idx) => (
                      <a
                        key={idx}
                        href={resource.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="resource-link"
                      >
                        <div className="resource-title">{resource.title}</div>
                        <div className="resource-meta">
                          {resource.type} • {resource.level}
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="roadmap-footer">
          <Link to="/progress" className="view-progress-link">
            View Detailed Progress →
          </Link>
        </div>
      </div>
    </div>
  )
}

export default Roadmap

