import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useToast } from '../components/ToastContainer'
import { QuestionnaireSkeleton } from '../components/LoadingSkeleton'
import './Questionnaire.css'

function AdaptiveQuestionnaire({ sessionId }) {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [currentQuestion, setCurrentQuestion] = useState(null)
  const [answers, setAnswers] = useState({})
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [questionsAnswered, setQuestionsAnswered] = useState(0)
  const [remainingJobs, setRemainingJobs] = useState(10)
  const [warmupActive, setWarmupActive] = useState(true)
  const [completed, setCompleted] = useState(false)

  useEffect(() => {
    // Start adaptive quiz (session is created by backend)
    axios.post('/api/adaptive/start')
      .then(response => {
        const newSessionId = response.data.session_id
        localStorage.setItem('sessionId', newSessionId)
        setCurrentQuestion(response.data.question)
        setRemainingJobs(response.data.remaining_jobs)
        setLoading(false)
      })
      .catch(error => {
        console.error('Failed to start adaptive quiz:', error)
        showToast('Failed to start adaptive quiz. Please try again.', 'error')
        setLoading(false)
      })
  }, [navigate, showToast])

  const handleAnswer = async (value) => {
    if (submitting || !currentQuestion) return

    setSubmitting(true)
    const answerValue = Array.isArray(value) ? value.join(',') : value
    const currentSessionId = localStorage.getItem('sessionId') || sessionId

    try {
      const response = await axios.post(`/api/adaptive/${currentSessionId}/answer`, {
        question_id: currentQuestion.id,
        answer_value: answerValue,
        answer_type: currentQuestion.answer_type
      })

      setAnswers({ ...answers, [currentQuestion.id]: value })

      if (response.data.completed) {
        // Quiz is complete, navigate to results
        setCompleted(true)
        showToast('Quiz complete! Loading your results...', 'success')
        // Store results in sessionStorage for Results page
        sessionStorage.setItem('adaptiveResults', JSON.stringify({
          top_5_jobs: response.data.top_5_jobs,
          questions_answered: response.data.questions_answered
        }))
        navigate('/results')
      } else {
        // Continue with next question
        setCurrentQuestion(response.data.question)
        setQuestionsAnswered(response.data.questions_answered)
        setRemainingJobs(response.data.remaining_jobs)
        setWarmupActive(response.data.warmup_active)
      }
    } catch (error) {
      console.error('Failed to submit answer:', error)
      const errorMessage = error.response?.data?.error || error.message || 'Unknown error'
      console.error('Error details:', {
        message: errorMessage,
        status: error.response?.status,
        data: error.response?.data,
        sessionId: currentSessionId,
        questionId: currentQuestion?.id,
        answerValue: answerValue
      })
      showToast(`Failed to submit answer: ${errorMessage}`, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading || completed) {
    return (
      <div className="questionnaire">
        <QuestionnaireSkeleton />
      </div>
    )
  }

  if (!currentQuestion) {
    return <div className="questionnaire-error">No question available</div>
  }

  const progress = questionsAnswered > 0 
    ? Math.min(100, (questionsAnswered / 20) * 100) 
    : 5 // Show some progress even at start

  const renderQuestionInput = () => {
    switch (currentQuestion.answer_type) {
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
                  className={`likert-button ${answers[currentQuestion.id] === num ? 'selected' : ''}`}
                  onClick={() => handleAnswer(num)}
                  disabled={submitting}
                >
                  <div className="likert-number">{num}</div>
                  <div className="likert-label">{labels[num]}</div>
                </button>
              )
            })}
          </div>
        )

      case 'SingleChoice':
        const options = currentQuestion.options ? currentQuestion.options.split(';') : []
        return (
          <div className="choice-options">
            {options.map((option, idx) => (
              <button
                key={idx}
                className={`choice-button ${answers[currentQuestion.id] === option ? 'selected' : ''}`}
                onClick={() => handleAnswer(option)}
                disabled={submitting}
              >
                {option}
              </button>
            ))}
          </div>
        )

      case 'MultiChoice':
        const multiOptions = currentQuestion.options ? currentQuestion.options.split(';') : []
        const selected = answers[currentQuestion.id] || []
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
                disabled={submitting}
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
              value={answers[currentQuestion.id] || ''}
              onChange={(e) => setAnswers({ ...answers, [currentQuestion.id]: parseInt(e.target.value) || 0 })}
              disabled={submitting}
            />
            <button 
              className="submit-numeric" 
              onClick={() => handleAnswer(answers[currentQuestion.id] || 0)}
              disabled={submitting}
            >
              {submitting ? 'Submitting...' : 'Next'}
            </button>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="questionnaire">
      <div className="questionnaire-container">
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${progress}%` }}></div>
        </div>
        <div className="question-header-info">
          <div className="question-number">
            Question {questionsAnswered + 1}
            {warmupActive && <span className="warmup-badge">Warmup</span>}
          </div>
          <div className="adaptive-stats">
            <span className="jobs-remaining">{remainingJobs} jobs remaining</span>
          </div>
        </div>
        <div className="question-content">
          <h2 className="question-text">{currentQuestion.question}</h2>
          <div className="question-input">
            {renderQuestionInput()}
          </div>
          {submitting && (
            <div className="submitting-indicator">
              Analyzing your answer...
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default AdaptiveQuestionnaire
