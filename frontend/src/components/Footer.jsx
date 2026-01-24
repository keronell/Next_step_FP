import { Link } from 'react-router-dom'
import './Footer.css'

function Footer() {
  return (
    <footer className="footer">
      <div className="footer-container">
        <div className="footer-content">
          <div className="footer-section">
            <h3 className="footer-title">NextStep Career Matcher</h3>
            <p className="footer-description">
              Take your career to the next level with personalized assessments and learning roadmaps.
            </p>
          </div>
          
          <div className="footer-section">
            <h4 className="footer-heading">Quick Links</h4>
            <ul className="footer-links">
              <li><Link to="/">Home</Link></li>
              <li><Link to="/questionnaire">Assessment</Link></li>
              <li><Link to="/results">Results</Link></li>
              <li><Link to="/roadmap">Roadmap</Link></li>
            </ul>
          </div>
          
          <div className="footer-section">
            <h4 className="footer-heading">Features</h4>
            <ul className="footer-links">
              <li>Target Roles</li>
              <li>Learning Pathways</li>
              <li>Technologies</li>
              <li>Career Roadmap</li>
            </ul>
          </div>
          
          <div className="footer-section">
            <h4 className="footer-heading">About</h4>
            <p className="footer-text">
              Helping you discover your ideal tech career path through AI-powered matching and personalized learning guidance.
            </p>
          </div>
        </div>
        
        <div className="footer-bottom">
          <p className="footer-copyright">
            © 2026 NextStep Career Matcher. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  )
}

export default Footer
