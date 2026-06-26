import { useEffect, useRef, useState } from 'react'
import { Sparkles, ChevronRight, ChevronLeft, SkipForward, Edit3, AlertTriangle, CheckCircle2, Lock } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { QUESTIONS } from '../data'
import { useReveal } from '../hooks/useReveal'
import Button from '../components/ui/Button.jsx'
import Eyebrow from '../components/ui/Eyebrow.jsx'
import { useAuth } from '../contexts/AuthContext'

// answers[qId] = number (answered) | null (skipped) | undefined (not visited)
const isAnswered = (val) => val !== null && val !== undefined
const isSkipped  = (val) => val === null

function Assessment({ phase, onStart, onComplete }) {
  const revealRef = useReveal(0.08)

  // All quiz state lives here
  const [currentQ, setCurrentQ] = useState(0)
  const [answers, setAnswers] = useState({})
  const [highWater, setHighWater] = useState(0)      // furthest question reached
  const [quizPhase, setQuizPhase] = useState('answering') // 'answering' | 'review'
  const [fromReview, setFromReview] = useState(false) // editing a single Q from review
  const [skipWarning, setSkipWarning] = useState(false)
  const [pendingVal, setPendingVal] = useState(null)  // value just clicked (animation)

  // Reset all quiz state when the parent resets to idle
  useEffect(() => {
    if (phase === 'idle') {
      setCurrentQ(0); setAnswers({}); setHighWater(0)
      setQuizPhase('answering'); setFromReview(false)
      setSkipWarning(false); setPendingVal(null)
    }
  }, [phase])

  // Pre-fill pending display when navigating to an already-visited question
  useEffect(() => {
    const existing = answers[QUESTIONS[currentQ]?.id]
    setPendingVal(isAnswered(existing) ? existing : null)
  }, [currentQ]) // eslint-disable-line react-hooks/exhaustive-deps

  const advanceOrReview = (newAnswers) => {
    if (fromReview) {
      setFromReview(false)
      setQuizPhase('review')
      setSkipWarning(false)
      return
    }
    if (currentQ < QUESTIONS.length - 1) {
      const next = currentQ + 1
      setCurrentQ(next)
      setHighWater((hw) => Math.max(hw, next))
    } else {
      setQuizPhase('review')
    }
  }

  const handleSelect = (value) => {
    if (pendingVal !== null && !fromReview) return // already selected, waiting to advance
    setPendingVal(value)
    const newAnswers = { ...answers, [QUESTIONS[currentQ].id]: value }
    setAnswers(newAnswers)
    setTimeout(() => advanceOrReview(newAnswers), 300)
  }

  const handleBack = () => {
    if (currentQ === 0) return
    setFromReview(false)
    setCurrentQ(currentQ - 1)
  }

  const handleSkip = () => {
    const newAnswers = { ...answers, [QUESTIONS[currentQ].id]: null }
    setAnswers(newAnswers)
    advanceOrReview(newAnswers)
  }

  const handleDotJump = (i) => {
    if (i === currentQ) return
    if (i > highWater && answers[QUESTIONS[i].id] === undefined) return
    setCurrentQ(i)
  }

  // Review actions
  const handleEditQuestion = (i) => {
    setCurrentQ(i)
    setFromReview(true)
    setSkipWarning(false)
    setQuizPhase('answering')
  }

  const handleGoBackToReview = () => {
    setFromReview(false)
    setQuizPhase('answering')
    // jump back to last question
    setCurrentQ(QUESTIONS.length - 1)
  }

  const handleSubmit = () => {
    const skippedCount = QUESTIONS.filter((q) => !isAnswered(answers[q.id])).length
    if (skippedCount > 0) {
      setSkipWarning(true)
      return
    }
    onComplete(answers)
  }

  const handleSubmitAnyway = () => onComplete(answers)

  const handleReviewSkipped = () => {
    const firstSkipped = QUESTIONS.findIndex((q) => !isAnswered(answers[q.id]))
    if (firstSkipped >= 0) {
      setCurrentQ(firstSkipped)
      setFromReview(true)
      setQuizPhase('answering')
      setSkipWarning(false)
    }
  }

  return (
    <section id="assessment" className="py-24 px-6">
      <div className="max-w-3xl mx-auto">
        <div ref={revealRef} className="reveal">
          {phase === 'idle' && <AssessmentStart onStart={onStart} />}

          {phase === 'assessing' && quizPhase === 'answering' && (
            <QuizCard
              currentQ={currentQ}
              answers={answers}
              highWater={highWater}
              pendingVal={pendingVal}
              fromReview={fromReview}
              onSelect={handleSelect}
              onBack={handleBack}
              onSkip={handleSkip}
              onDotJump={handleDotJump}
            />
          )}

          {phase === 'assessing' && quizPhase === 'review' && (
            <ReviewScreen
              answers={answers}
              skipWarning={skipWarning}
              onEdit={handleEditQuestion}
              onGoBack={handleGoBackToReview}
              onSubmit={handleSubmit}
              onSubmitAnyway={handleSubmitAnyway}
              onReviewSkipped={handleReviewSkipped}
            />
          )}

          {phase === 'loading' && <LoadingScreen />}
        </div>
      </div>
    </section>
  )
}

// ─── Start card ────────────────────────────────────────────────────────────────

function AssessmentStart({ onStart }) {
  const { user, authLoading } = useAuth()
  const isLocked = !authLoading && !user

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
      className="flex flex-col items-center text-center"
    >
      <Eyebrow dot className="mb-4">Career Assessment</Eyebrow>
      <h2 className="font-display font-bold text-h1 text-navy mb-5 tracking-tight text-balance">
        Find your ideal
        <br />
        <span className="italic text-gold">tech career</span>
      </h2>
      <p className="font-body text-navy/65 text-body max-w-[52ch] mx-auto leading-snug mb-10">
        10 questions · 3–5 minutes
      </p>
      <div className="flex flex-wrap justify-center gap-2 mb-10">
        {['Skills & interests', 'Work style', 'Personality fit', 'Personalized match'].map((tag) => (
          <span key={tag} className="px-3 py-1 rounded-full bg-navy/[0.04] border border-navy/10 text-eyebrow font-body text-navy/65 font-medium uppercase">
            {tag}
          </span>
        ))}
      </div>
      <Button variant="primary" size="lg" onClick={onStart}>
        {isLocked ? (
          <>
            <Lock size={16} aria-hidden="true" />
            Sign in to Begin
          </>
        ) : (
          <>
            <Sparkles size={16} aria-hidden="true" />
            Begin Assessment
            <ChevronRight size={16} aria-hidden="true" />
          </>
        )}
      </Button>
    </motion.div>
  )
}

// ─── Quiz card ─────────────────────────────────────────────────────────────────

function QuizCard({ currentQ, answers, highWater, pendingVal, fromReview, onSelect, onBack, onSkip, onDotJump }) {
  const question = QUESTIONS[currentQ]
  const progressPct = ((currentQ) / QUESTIONS.length) * 100
  const isWaiting = pendingVal !== null && !fromReview && isAnswered(pendingVal)

  return (
    <div className="bg-white rounded-card border border-navy/[0.08] shadow-lg overflow-hidden">
      {/* Top progress bar */}
      <div className="h-1 bg-navy/[0.08]">
        <motion.div
          className="h-full bg-gradient-to-r from-gold to-gold-light"
          initial={false}
          animate={{ width: `${progressPct}%` }}
          transition={{ type: 'spring', stiffness: 120, damping: 24 }}
        />
      </div>

      <div className="p-8 md:p-10">
        {/* From-review badge */}
        {fromReview && (
          <div className="flex items-center gap-2 mb-4 px-3 py-1.5 bg-gold/10 border border-gold/40 rounded-full w-fit">
            <Edit3 size={12} className="text-gold" aria-hidden="true" />
            <span className="font-body text-eyebrow font-semibold text-gold uppercase">Editing — will return to Review</span>
          </div>
        )}

        <AnimatePresence mode="wait">
          <motion.div
            key={currentQ}
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -24 }}
            transition={{ duration: 0.28, ease: [0.25, 0.46, 0.45, 0.94] }}
          >
        {/* Category + counter */}
        <div className="flex items-center justify-between mb-6">
          <Eyebrow dot>{question.category}</Eyebrow>
          <span className="font-body text-small text-navy/55 tabular">
            <span className="font-semibold text-navy/80">{currentQ + 1}</span>
            <span className="mx-0.5">/</span>
            {QUESTIONS.length}
          </span>
        </div>

        {/* Question */}
        <h2 className="font-display font-semibold text-h2 md:text-h1 text-navy leading-snug mb-8 tracking-tight text-balance">
          {question.text}
        </h2>

        {/* Options */}
        <div className="option-grid grid grid-cols-1 sm:grid-cols-2 gap-3 mb-8">
          {question.options.map((option, i) => {
            const isHighlighted = pendingVal === option.value
            const isPreviousAnswer = isAnswered(answers[question.id]) && answers[question.id] === option.value && pendingVal === null
            const showSelected = isHighlighted || isPreviousAnswer
            return (
              <button
                key={i}
                onClick={() => onSelect(option.value)}
                disabled={isWaiting}
                className={`focus-ring text-left p-4 rounded-2xl border-2 font-body text-base leading-snug transition-all duration-base
                  ${showSelected
                    ? 'border-gold bg-gold/[0.08] text-navy shadow-sm ring-1 ring-gold/60'
                    : 'border-navy/10 bg-cream/50 text-navy/75 hover:border-gold/60 hover:bg-gold/5 hover:text-navy hover:scale-[1.01]'
                  }
                  ${isWaiting && !showSelected ? 'opacity-40 cursor-not-allowed' : ''}
                `}
              >
                <div className="flex items-start gap-3">
                  <div className={`mt-0.5 w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-all duration-fast
                    ${showSelected ? 'border-gold bg-gold' : 'border-navy/25'}`}
                  >
                    {showSelected && <div className="w-1.5 h-1.5 rounded-full bg-cream" />}
                  </div>
                  <span>{option.label}</span>
                </div>
              </button>
            )
          })}
        </div>
          </motion.div>
        </AnimatePresence>

        {/* Clickable progress dots */}
        <div className="flex justify-center items-center gap-1.5 mb-6">
          {QUESTIONS.map((q, i) => {
            const val = answers[q.id]
            const isCurrentDot = i === currentQ
            const isVisited = i <= highWater || val !== undefined
            const answered = isAnswered(val)
            const skipped = isSkipped(val)
            const clickable = isVisited && !isCurrentDot

            return (
              <button
                key={i}
                onClick={() => clickable && onDotJump(i)}
                disabled={!clickable}
                title={isVisited ? (answered ? 'Jump to this question' : skipped ? 'Skipped — click to revisit' : '') : ''}
                aria-label={`Question ${i + 1}`}
                aria-current={isCurrentDot ? 'step' : undefined}
                className={`focus-ring rounded-full transition-all duration-base
                  ${isCurrentDot ? 'w-6 h-2.5 scale-[1.15]' : 'w-2.5 h-2.5'}
                  ${clickable ? 'cursor-pointer hover:scale-125' : 'cursor-default'}
                  ${isCurrentDot
                    ? 'bg-gold shadow-[0_0_0_3px_rgba(201,168,76,0.18)]'
                    : answered
                    ? 'bg-gold/70'
                    : skipped
                    ? 'bg-navy/25'
                    : 'bg-navy/[0.12]'
                  }
                `}
              />
            )
          })}
        </div>

        {/* Navigation row: Back · Skip */}
        <div className="flex items-center justify-between pt-4 border-t border-navy/[0.06]">
          <button
            onClick={onBack}
            disabled={currentQ === 0}
            className={`focus-ring inline-flex items-center gap-1.5 px-4 py-2 rounded-xl font-body text-small font-medium transition-all duration-fast
              ${currentQ === 0
                ? 'text-navy/30 cursor-not-allowed'
                : 'text-navy/65 hover:text-navy hover:bg-navy/[0.04]'
              }`}
          >
            <ChevronLeft size={15} aria-hidden="true" />
            Back
          </button>

          <button
            onClick={onSkip}
            className="focus-ring inline-flex items-center gap-1.5 px-4 py-2 rounded-xl font-body text-small font-medium text-navy/55 hover:text-navy/80 hover:bg-navy/[0.04] transition-all duration-fast"
          >
            {fromReview ? 'Skip & Return' : 'Skip'}
            <SkipForward size={15} aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Review screen ─────────────────────────────────────────────────────────────

function ReviewScreen({ answers, skipWarning, onEdit, onGoBack, onSubmit, onSubmitAnyway, onReviewSkipped }) {
  const skippedCount = QUESTIONS.filter((q) => !isAnswered(answers[q.id])).length

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
      className="bg-white rounded-card border border-navy/[0.08] shadow-lg overflow-hidden flex flex-col"
    >
      {/* Header */}
      <div className="px-8 pt-8 pb-5 border-b border-navy/[0.06]">
        <Eyebrow dot className="mb-2">
          <CheckCircle2 size={14} className="text-gold" aria-hidden="true" />
          Almost there
        </Eyebrow>
        <h2 className="font-display font-bold text-h2 md:text-h1 text-navy tracking-tight text-balance">
          Review your answers
        </h2>
        <p className="font-body text-small text-navy/55 mt-2 tabular">
          {skippedCount > 0
            ? `${QUESTIONS.length - skippedCount} answered · ${skippedCount} skipped`
            : `All ${QUESTIONS.length} questions answered`
          }
        </p>
      </div>

      {/* Scrollable question list */}
      <div className="overflow-y-auto max-h-[420px] divide-y divide-navy/[0.05]">
        {QUESTIONS.map((q, i) => {
          const val = answers[q.id]
          const answered = isAnswered(val)
          const selectedOption = answered ? q.options.find((o) => o.value === val) : null

          return (
            <div key={q.id} className="flex items-start gap-4 px-8 py-4 hover:bg-navy/[0.04] transition-colors duration-fast group">
              {/* Number */}
              <span className="font-body text-eyebrow font-semibold text-navy/40 tabular w-5 flex-shrink-0 pt-0.5">
                {String(i + 1).padStart(2, '0')}
              </span>

              {/* Q + A */}
              <div className="flex-1 min-w-0">
                <p className="font-body text-body font-medium text-navy leading-snug">
                  {q.text}
                </p>
                <p className={`font-body text-small mt-1 ${answered ? 'text-navy/65' : 'text-navy/40 italic'}`}>
                  {answered ? selectedOption?.label : 'Skipped'}
                </p>
              </div>

              {/* Edit */}
              <button
                onClick={() => onEdit(i)}
                className="focus-ring flex-shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-lg text-eyebrow font-body font-semibold uppercase text-navy/50 hover:text-gold hover:bg-gold/[0.08] border border-transparent hover:border-gold/30 transition-all duration-fast opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
              >
                <Edit3 size={11} aria-hidden="true" />
                Edit
              </button>
            </div>
          )
        })}
      </div>

      {/* Validation warning */}
      {skipWarning && (
        <div className="mx-6 mt-4 p-4 rounded-xl bg-amber-50 border border-amber-200 flex flex-col gap-3" role="alert">
          <div className="flex items-start gap-2.5">
            <AlertTriangle size={16} className="text-amber-500 flex-shrink-0 mt-0.5" aria-hidden="true" />
            <p className="font-body text-small text-amber-800 leading-snug">
              You have <span className="font-semibold">{skippedCount} unanswered question{skippedCount > 1 ? 's' : ''}</span>.
              You can still submit or go back to answer them.
            </p>
          </div>
          <div className="flex gap-2 pl-6">
            <button
              onClick={onSubmitAnyway}
              className="focus-ring px-4 py-2 rounded-lg bg-amber-500 text-white font-body text-eyebrow font-semibold uppercase hover:bg-amber-600 transition-colors duration-fast"
            >
              Submit Anyway
            </button>
            <button
              onClick={onReviewSkipped}
              className="focus-ring px-4 py-2 rounded-lg border border-amber-300 text-amber-700 font-body text-eyebrow font-semibold uppercase hover:bg-amber-100 transition-colors duration-fast"
            >
              Review Skipped
            </button>
          </div>
        </div>
      )}

      {/* Sticky bottom bar */}
      <div className="px-6 py-5 border-t border-navy/[0.06] bg-cream/60 flex flex-col sm:flex-row items-stretch sm:items-center gap-3 mt-4">
        <Button variant="secondary" size="md" onClick={onGoBack} className="!rounded-xl">
          <ChevronLeft size={15} aria-hidden="true" />
          Go Back
        </Button>
        <Button variant="primary" size="md" onClick={onSubmit} className="!rounded-xl flex-1 sm:flex-none">
          Submit & See Results
          <ChevronRight size={15} aria-hidden="true" />
        </Button>
      </div>
    </motion.div>
  )
}

// ─── Scan grid (Style B) ───────────────────────────────────────────────────────

function ScanGrid() {
  const svgRef = useRef(null)

  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const ns = 'http://www.w3.org/2000/svg'
    const segs = [
      [20, 20, 70, 20], [20, 20, 20, 70],
      [210, 20, 160, 20], [210, 20, 210, 70],
      [20, 210, 70, 210], [20, 210, 20, 160],
      [210, 210, 160, 210], [210, 210, 210, 160],
      [95, 80, 95, 150], [135, 80, 135, 150],
    ]
    const lines = segs.map((s, i) => {
      const el = document.createElementNS(ns, 'line')
      el.setAttribute('x1', s[0]); el.setAttribute('y1', s[1])
      el.setAttribute('x2', s[2]); el.setAttribute('y2', s[3])
      const len = Math.sqrt((s[2] - s[0]) ** 2 + (s[3] - s[1]) ** 2)
      el.style.stroke = i < 8 ? 'var(--color-gold)' : 'rgba(201,168,76,0.25)'
      el.setAttribute('stroke-width', i < 8 ? '1.5' : '0.8')
      el.setAttribute('stroke-dasharray', `${len}`)
      el.setAttribute('stroke-dashoffset', `${len}`)
      el.style.transition = `stroke-dashoffset ${0.5 + i * 0.06}s ${i * 0.05}s cubic-bezier(0.4,0,0.2,1)`
      svg.appendChild(el)
      return el
    })
    const raf = requestAnimationFrame(() =>
      requestAnimationFrame(() =>
        lines.forEach(l => l.setAttribute('stroke-dashoffset', '0'))
      )
    )
    return () => { cancelAnimationFrame(raf); lines.forEach(l => l.remove()) }
  }, [])

  return (
    <div className="relative flex items-center justify-center mb-8">
      <svg ref={svgRef} width={230} height={230} viewBox="0 0 230 230" />
      <div className="absolute inset-0 flex items-start justify-center pointer-events-none overflow-hidden">
        <div className="w-full h-px bg-gradient-to-r from-transparent via-gold/50 to-transparent animate-scan-line" />
      </div>
    </div>
  )
}

// ─── Loading screen ─────────────────────────────────────────────────────────────

function LoadingScreen() {
  const [progress, setProgress] = useState(0)
  const [reduceMotion, setReduceMotion] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setProgress(96), 50)
    return () => clearTimeout(t)
  }, [])

  useEffect(() => {
    setReduceMotion(window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  }, [])

  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      {reduceMotion ? (
        <ScanGrid />
      ) : (
        <div className="relative mb-8 w-[230px] h-[230px] rounded-2xl overflow-hidden border border-gold/25 shadow-sm">
          <video
            src="/video/loading.mp4"
            poster="/video/loading-poster.png"
            autoPlay
            muted
            loop
            playsInline
            aria-hidden="true"
            className="w-full h-full object-cover"
          />
        </div>
      )}
      <Eyebrow dot className="mb-4">Analyzing your responses</Eyebrow>
      <div className="flex font-display font-semibold text-h2 text-navy mb-2 tracking-tight" aria-label="Analyzing your profile">
        {'Analyzing your profile…'.split('').map((ch, i) => (
          <span
            key={i}
            className="char-stamp inline-block"
            style={{ animationDelay: `${i * 0.035}s` }}
          >
            {ch === ' ' ? ' ' : ch}
          </span>
        ))}
      </div>
      <p className="font-body text-small text-navy/60 mb-8 max-w-xs leading-snug">
        Matching your answers against 6 tech career paths
      </p>
      <div className="w-64 h-1.5 bg-navy/[0.1] rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-gold to-gold-light rounded-full transition-[width] ease-out"
          style={{ width: `${progress}%`, transitionDuration: '2400ms' }}
        />
      </div>
      <p className="font-body text-eyebrow uppercase text-navy/50 mt-3 tabular">{progress}%</p>
    </div>
  )
}

export default Assessment
