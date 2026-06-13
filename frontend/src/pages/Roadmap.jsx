import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import axios from 'axios'
import { useToast } from '../components/ToastContainer'
import { RoadmapSkeleton } from '../components/LoadingSkeleton'
import './Roadmap.css'

function Roadmap({ sessionId }) {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [roadmap, setRoadmap] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get session ID from localStorage (may have been updated by adaptive quiz)
    const currentSessionId = localStorage.getItem('sessionId') || sessionId
    
    if (!currentSessionId) {
      navigate('/')
      return
    }

    console.log('Roadmap page - fetching roadmap for session:', currentSessionId)
    axios.get(`/api/sessions/${currentSessionId}/roadmap`)
      .then(response => {
        console.log('Roadmap loaded successfully:', response.data)
        setRoadmap(response.data)
        setLoading(false)
      })
      .catch(error => {
        console.error('Failed to load roadmap:', error)
        console.error('Error details:', {
          message: error.message,
          status: error.response?.status,
          data: error.response?.data,
          sessionId: currentSessionId
        })
        setLoading(false)
      })
  }, [sessionId, navigate])

  const handleCompleteStep = async (itemId, currentStatus) => {
    const newStatus = currentStatus === 'completed' ? 'pending' : 'completed'
    
    try {
      await axios.patch(`/api/roadmap-items/${itemId}`, { status: newStatus })
      
      // Get current session ID from localStorage
      const currentSessionId = localStorage.getItem('sessionId') || sessionId
      
      // Reload roadmap to get updated progress
      const response = await axios.get(`/api/sessions/${currentSessionId}/roadmap`)
      setRoadmap(response.data)
      showToast(
        newStatus === 'completed' ? 'Step marked as completed!' : 'Step marked as pending',
        'success'
      )
    } catch (error) {
      console.error('Failed to update step:', error)
      showToast('Failed to update step. Please try again.', 'error')
    }
  }

  const handleShare = () => {
    const url = window.location.href
    if (navigator.share) {
      navigator.share({
        title: `My ${roadmap.role_name} Learning Roadmap`,
        text: `Check out my learning roadmap for ${roadmap.role_name}! Progress: ${roadmap.progress}%`,
        url: url
      }).catch(() => {
        copyToClipboard(url)
      })
    } else {
      copyToClipboard(url)
    }
  }

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      showToast('Link copied to clipboard!', 'success')
    }).catch(() => {
      showToast('Failed to copy link', 'error')
    })
  }

  const handleExportPDF = () => {
    showToast('PDF export feature coming soon!', 'info')
    // Future implementation: Use a library like jsPDF or html2pdf
  }

  const handleExportImage = () => {
    showToast('Image export feature coming soon!', 'info')
    // Future implementation: Use html2canvas to capture and download
  }

  if (loading) {
    return (
      <div className="roadmap">
        <div className="roadmap-hero-bg"></div>
        <RoadmapSkeleton />
      </div>
    )
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
          <div className="roadmap-header-top">
            <Link to="/results" className="roadmap-back-button">
              ← Back to Results
            </Link>
            <div className="roadmap-actions">
              <button className="roadmap-action-button" onClick={handleShare} title="Share roadmap">
                📤 Share
              </button>
              <button className="roadmap-action-button" onClick={handleExportPDF} title="Export as PDF">
                📄 PDF
              </button>
              <button className="roadmap-action-button" onClick={handleExportImage} title="Export as Image">
                🖼️ Image
              </button>
            </div>
          </div>
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

