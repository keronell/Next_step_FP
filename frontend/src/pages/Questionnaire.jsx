import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useToast } from '../components/ToastContainer'
import { QuestionnaireSkeleton } from '../components/LoadingSkeleton'
import './Questionnaire.css'

function Questionnaire({ sessionId }) {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [questions, setQuestions] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState({})
  const [loading, setLoading] = useState(true)
  const [showSidebar, setShowSidebar] = useState(true)
  const [showReview, setShowReview] = useState(false)
  const [skippedQuestions, setSkippedQuestions] = useState(new Set())

  useEffect(() => {
    if (!sessionId) {
      navigate('/')
      return
    }

    axios.get('/api/questions')
      .then(response => {
        setQuestions(response.data)
        setLoading(false)
      })
      .catch(error => {
        console.error('Failed to load questions:', error)
        setLoading(false)
      })
  }, [sessionId, navigate])

  const handleAnswer = async (value) => {
    const question = questions[currentIndex]
    const answerValue = Array.isArray(value) ? value.join(',') : value

    try {
      await axios.post(`/api/sessions/${sessionId}/answers`, {
        question_id: question.id,
        answer_value: answerValue,
        answer_type: question.answer_type
      })

      setAnswers({ ...answers, [question.id]: value })
      setSkippedQuestions(prev => {
        const newSet = new Set(prev)
        newSet.delete(question.id)
        return newSet
      })

      if (currentIndex < questions.length - 1) {
        setCurrentIndex(currentIndex + 1)
      } else {
        // All questions answered, show review
        setShowReview(true)
      }
    } catch (error) {
      console.error('Failed to submit answer:', error)
    }
  }

  const handlePrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
    }
  }

  const handleSkip = () => {
    const question = questions[currentIndex]
    setSkippedQuestions(prev => new Set(prev).add(question.id))
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1)
    } else {
      setShowReview(true)
    }
  }

  const handleGoToQuestion = (index) => {
    setCurrentIndex(index)
    setShowReview(false)
  }

  const handleSubmitReview = async () => {
    try {
      showToast('Computing your results...', 'info', 2000)
      await axios.post(`/api/sessions/${sessionId}/compute`)
      showToast('Results ready!', 'success')
      navigate('/results')
    } catch (error) {
      console.error('Failed to compute results:', error)
      showToast('Failed to compute results. Please try again.', 'error')
    }
  }

  const handleEditAnswer = (index) => {
    setCurrentIndex(index)
    setShowReview(false)
  }

  const getAnswerDisplay = (question, answer) => {
    if (!answer && answer !== 0) return 'Not answered'
    
    switch (question.answer_type) {
      case 'Likert5':
        const labels = {
          1: 'Strongly disagree',
          2: 'Disagree',
          3: 'Neutral',
          4: 'Agree',
          5: 'Strongly agree'
        }
        return `${answer} - ${labels[answer]}`
      case 'SingleChoice':
        return answer
      case 'MultiChoice':
        return Array.isArray(answer) ? answer.join(', ') : answer
      case 'Numeric':
        return answer.toString()
      default:
        return answer?.toString() || 'Not answered'
    }
  }

  if (loading) {
    return (
      <div className="questionnaire">
        <QuestionnaireSkeleton />
      </div>
    )
  }

  if (questions.length === 0) {
    return <div className="questionnaire-error">No questions available</div>
  }

  const question = questions[currentIndex]
  const progress = ((currentIndex + 1) / questions.length) * 100

  const renderQuestionInput = () => {
    switch (question.answer_type) {
      case 'Likert5':
        return (
          <div className="likert-scale">
            {[1, 2, 3, 4, 5].map(num => {
              const labels = {
                1: 'Strongly disagree',
                2: 'Disagree',
                3: 'Neutral',
                4: 'Agree',
                5: 'Strongly agree'
              }
              return (
                <button
                  key={num}
                  className={`likert-button ${answers[question.id] === num ? 'selected' : ''}`}
                  onClick={() => handleAnswer(num)}
                >
                  <div className="likert-number">{num}</div>
                  <div className="likert-label">{labels[num]}</div>
                </button>
              )
            })}
          </div>
        )

      case 'SingleChoice':
        const options = question.options.split(';')
        return (
          <div className="choice-options">
            {options.map((option, idx) => (
              <button
                key={idx}
                className={`choice-button ${answers[question.id] === option ? 'selected' : ''}`}
                onClick={() => handleAnswer(option)}
              >
                {option}
              </button>
            ))}
          </div>
        )

      case 'MultiChoice':
        const multiOptions = question.options.split(';')
        const selected = answers[question.id] || []
        return (
          <div className="choice-options">
            {multiOptions.map((option, idx) => (
              <button
                key={idx}
                className={`choice-button ${selected.includes(option) ? 'selected' : ''}`}
                onClick={() => {
                  const newSelected = selected.includes(option)
                    ? selected.filter(o => o !== option)
                    : [...selected, option]
                  handleAnswer(newSelected)
                }}
              >
                {option}
              </button>
            ))}
          </div>
        )

      case 'Numeric':
        return (
          <div className="numeric-input">
            <input
              type="number"
              min="0"
              value={answers[question.id] || ''}
              onChange={(e) => setAnswers({ ...answers, [question.id]: parseInt(e.target.value) || 0 })}
              onBlur={async () => {
                const value = answers[question.id]
                if (value !== undefined && value !== null && value !== '' && value !== 0) {
                  await handleAnswer(value)
                }
              }}
            />
            <button className="submit-numeric" onClick={async () => {
              const value = answers[question.id] || 0
              if (value !== undefined && value !== null && value !== '') {
                await handleAnswer(value)
              } else {
                if (currentIndex < questions.length - 1) {
                  setCurrentIndex(currentIndex + 1)
                } else {
                  setShowReview(true)
                }
              }
            }}>
              Next
            </button>
          </div>
        )

      default:
        return null
    }
  }

  if (showReview) {
    return (
      <div className="questionnaire">
        <div className="questionnaire-container review-container">
          <h1 className="review-title">Review Your Answers</h1>
          <p className="review-subtitle">Please review all your answers before submitting</p>
          
          <div className="review-questions">
            {questions.map((q, index) => {
              const answer = answers[q.id]
              const isSkipped = skippedQuestions.has(q.id)
              return (
                <div key={q.id} className="review-question-item">
                  <div className="review-question-header">
                    <span className="review-question-number">Question {index + 1}</span>
                    {isSkipped && <span className="review-skipped-badge">Skipped</span>}
                  </div>
                  <h3 className="review-question-text">{q.question}</h3>
                  <div className="review-answer">
                    <strong>Your Answer:</strong> {isSkipped ? 'Skipped' : getAnswerDisplay(q, answer)}
                  </div>
                  <button 
                    className="review-edit-button"
                    onClick={() => handleEditAnswer(index)}
                  >
                    Edit Answer
                  </button>
                </div>
              )
            })}
          </div>

          <div className="review-actions">
            <button className="review-button secondary" onClick={() => setShowReview(false)}>
              Back to Questions
            </button>
            <button className="review-button primary" onClick={handleSubmitReview}>
              Submit Assessment
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="questionnaire">
      <button 
        className="sidebar-toggle"
        onClick={() => setShowSidebar(!showSidebar)}
        aria-label="Toggle sidebar"
      >
        {showSidebar ? '◀' : '▶'}
      </button>

      {showSidebar && (
        <div className="questionnaire-sidebar">
          <h3 className="sidebar-title">Questions</h3>
          <div className="sidebar-questions">
            {questions.map((q, index) => {
              const isAnswered = answers[q.id] !== undefined && answers[q.id] !== null && answers[q.id] !== ''
              const isSkipped = skippedQuestions.has(q.id)
              const isCurrent = index === currentIndex
              
              return (
                <button
                  key={q.id}
                  className={`sidebar-question-item ${isCurrent ? 'current' : ''} ${isAnswered ? 'answered' : ''} ${isSkipped ? 'skipped' : ''}`}
                  onClick={() => handleGoToQuestion(index)}
                >
                  <span className="sidebar-question-number">{index + 1}</span>
                  <span className="sidebar-question-status">
                    {isSkipped ? '⏭️' : isAnswered ? '✓' : '○'}
                  </span>
                </button>
              )
            })}
          </div>
          <div className="sidebar-progress">
            <div className="sidebar-progress-text">
              {Object.keys(answers).filter(id => answers[id] !== undefined && answers[id] !== null && answers[id] !== '').length} / {questions.length} answered
            </div>
          </div>
        </div>
      )}

      <div className="questionnaire-container">
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${progress}%` }}></div>
        </div>
        <div className="question-number">
          Question {currentIndex + 1} of {questions.length}
        </div>
        <div className="question-content">
          <h2 className="question-text">{question.question}</h2>
          {question.category && (
            <div className="question-meta">
              {question.category} • {question.subcategory}
            </div>
          )}
          <div className="question-input">
            {renderQuestionInput()}
          </div>
          <div className="question-actions">
            <button 
              className="question-action-button secondary"
              onClick={handlePrevious}
              disabled={currentIndex === 0}
            >
              ← Previous
            </button>
            <button 
              className="question-action-button secondary"
              onClick={handleSkip}
            >
              Skip Question
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Questionnaire

