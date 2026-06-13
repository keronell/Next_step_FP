import { Link } from 'react-router-dom'
import './NotFound.css'

function NotFound() {
  return (
    <div className="not-found">
      <div className="not-found-container">
        <div className="not-found-content">
          <div className="not-found-illustration">
            <div className="not-found-number">404</div>
            <div className="not-found-icon">🔍</div>
          </div>
          <h1 className="not-found-title">Page Not Found</h1>
          <p className="not-found-description">
            Oops! The page you're looking for doesn't exist or has been moved.
          </p>
          <div className="not-found-actions">
            <Link to="/" className="not-found-button primary">
              Go to Home
            </Link>
            <Link to="/questionnaire" className="not-found-button secondary">
              Start Assessment
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default NotFound
