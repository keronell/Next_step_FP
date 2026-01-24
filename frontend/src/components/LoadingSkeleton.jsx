import './LoadingSkeleton.css'

export function QuestionnaireSkeleton() {
  return (
    <div className="skeleton-container">
      <div className="skeleton-progress-bar">
        <div className="skeleton-shimmer"></div>
      </div>
      <div className="skeleton-question-number"></div>
      <div className="skeleton-question-text"></div>
      <div className="skeleton-options">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="skeleton-option"></div>
        ))}
      </div>
    </div>
  )
}

export function ResultsSkeleton() {
  return (
    <div className="skeleton-container">
      <div className="skeleton-title"></div>
      <div className="skeleton-subtitle"></div>
      <div className="skeleton-grid">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="skeleton-card">
            <div className="skeleton-card-header">
              <div className="skeleton-badge"></div>
              <div className="skeleton-badge"></div>
            </div>
            <div className="skeleton-card-title"></div>
            <div className="skeleton-card-text"></div>
            <div className="skeleton-card-text short"></div>
            <div className="skeleton-button"></div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function RoadmapSkeleton() {
  return (
    <div className="skeleton-container">
      <div className="skeleton-title"></div>
      <div className="skeleton-progress-bar large"></div>
      <div className="skeleton-steps">
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div key={i} className="skeleton-step">
            <div className="skeleton-step-number"></div>
            <div className="skeleton-step-content">
              <div className="skeleton-step-title"></div>
              <div className="skeleton-step-text"></div>
              <div className="skeleton-step-text short"></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function ProgressSkeleton() {
  return (
    <div className="skeleton-container">
      <div className="skeleton-title"></div>
      <div className="skeleton-summary-cards">
        {[1, 2, 3].map(i => (
          <div key={i} className="skeleton-summary-card"></div>
        ))}
      </div>
      <div className="skeleton-progress-steps">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="skeleton-progress-step">
            <div className="skeleton-checkbox"></div>
            <div className="skeleton-step-info">
              <div className="skeleton-step-title"></div>
              <div className="skeleton-step-text"></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
