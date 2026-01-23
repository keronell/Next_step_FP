import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import './Questionnaire.css'

function Questionnaire({ sessionId }) {
  const navigate = useNavigate()
  const [questions, setQuestions] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState({})
  const [loading, setLoading] = useState(true)

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

      if (currentIndex < questions.length - 1) {
        setCurrentIndex(currentIndex + 1)
      } else {
        // All questions answered, compute results
        await computeResults()
      }
    } catch (error) {
      console.error('Failed to submit answer:', error)
    }
  }

  const computeResults = async () => {
    try {
      await axios.post(`/api/sessions/${sessionId}/compute`)
      navigate('/results')
    } catch (error) {
      console.error('Failed to compute results:', error)
      alert('Failed to compute results. Please try again.')
    }
  }

  if (loading) {
    return <div className="questionnaire-loading">Loading questions...</div>
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
              onBlur={() => handleAnswer(answers[question.id] || 0)}
            />
            <button className="submit-numeric" onClick={() => {
              if (currentIndex < questions.length - 1) {
                setCurrentIndex(currentIndex + 1)
              } else {
                computeResults()
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

  return (
    <div className="questionnaire">
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
        </div>
      </div>
    </div>
  )
}

export default Questionnaire

