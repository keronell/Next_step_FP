import { useEffect, useRef, useState } from 'react'
import Header from './components/Header'
import Footer from './components/Footer'
import Hero from './pages/Landing'
import HowItWorks from './pages/HowItWorks'
import Assessment from './pages/Questionnaire'
import Profile from './pages/Profile'
import Results from './pages/Results'
import Roadmap from './pages/Roadmap'
import History from './pages/History'
import AuthModal from './pages/AuthModal'
import { computeResults } from './data'
import { submitQuestionnaire, selectCareer, fetchMySubmissions } from './api'
import { useAuth } from './contexts/AuthContext'

function App() {
  const { user, authLoading } = useAuth()

  const [phase, setPhase] = useState('idle')
  const [results, setResults] = useState(null)
  const [notice, setNotice] = useState(null)
  const [selectedCareer, setSelectedCareer] = useState(null)
  const [activeTooltip, setActiveTooltip] = useState(null)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  // Answers are held between the quiz and the profile step, then submitted
  // together; `profile` is kept so the roadmap can personalize from it too.
  const [answers, setAnswers] = useState(null)
  const [profile, setProfile] = useState(null)

  // Monotonic id for the active run. Every async continuation captures it before
  // awaiting and re-checks it after, so work belonging to a run the user has
  // abandoned (reset, sign-out, account switch) can never write into the run that
  // replaced it. A full match takes several seconds, so these windows are wide.
  const runIdRef = useRef(0)
  useEffect(() => { runIdRef.current += 1 }, [user])

  // Live mirrors of the run's identity, readable from a callback whose closure was
  // frozen at an earlier render. A child's own guard cannot be authoritative here:
  // this component invalidates a run SYNCHRONOUSLY (handleReset) while a child
  // invalidates in a passive effect, so between those two moments the child still
  // believes its run is current. App owns the run, so App decides.
  const phaseRef = useRef(phase)
  phaseRef.current = phase
  const answersRef = useRef(answers)
  answersRef.current = answers

  // Was the run started by a signed-in user? signOut() deletes the access token
  // SYNCHRONOUSLY and only then calls setUser(null), so during that gap every
  // React-state guard above still reads the old run as current while api.js has
  // already lost the credential. Submitting there sends the run anonymously with
  // the browser session_id — which survives sign-out — and the next account to
  // sign in claims it via claimSessions(). localStorage is the only signal that
  // changes in step with the transition.
  //
  // Presence, not token identity: a future refresh flow would rotate the value
  // mid-run, and a false reject would silently swallow a legitimate submission.
  const runStartedAuthedRef = useRef(false)

  const assessmentRef = useRef(null)
  const profileRef = useRef(null)
  const resultsRef = useRef(null)
  const roadmapRef = useRef(null)
  const historyRef = useRef(null)

  const scrollTo = (ref) => {
    setTimeout(() => ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
  }

  // Restore the last results view on refresh. Runs once auth resolves; only acts
  // while idle so we never clobber an active flow. handleLoadHistory is omitted
  // from the deps on purpose (it's a new fn each render).
  useEffect(() => {
    if (authLoading || phase !== 'idle') return
    // The fetch outlives a sign-out: without this the previous account's
    // recommendations AND profile snapshot get restored after the sign-out effect
    // cleared state, which also leaves phase !== 'idle' so the NEW account's
    // restore is skipped entirely. `user` is a dep, so signing out runs the
    // cleanup; the run token additionally covers an explicit reset mid-flight.
    let cancelled = false
    const runId = runIdRef.current
    if (user) {
      fetchMySubmissions()
        .then((subs) => {
          if (cancelled || runIdRef.current !== runId) return
          if (!subs?.length) return
          const latest = [...subs].sort(
            (a, b) => new Date(b.created_at) - new Date(a.created_at),
          )[0]
          handleLoadHistory(
            latest.recommendations,
            latest.selected_career ?? null,
            latest.profile ?? null,
          )
        })
        .catch(() => {})
      return () => { cancelled = true }
    } else {
      let recs = null
      try { recs = JSON.parse(localStorage.getItem('nextstep_last_recommendations')) } catch {} // eslint-disable-line no-empty
      if (recs?.length) handleLoadHistory(recs, localStorage.getItem('nextstep_last_career') || null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, user])

  // Mirror anonymous users' last results to localStorage so a refresh can restore
  // them. Logged-in users use server history, so we never write their data here.
  // Waits for authLoading like the restore effect above - otherwise the initial
  // idle render clears the keys before the restore effect gets to read them.
  const prevUserRef = useRef(user)
  useEffect(() => {
    // On sign-out (truthy user -> null), clear the anonymous restore keys AND
    // drop the signed-out user's results view. Skipping the write on just this
    // render isn't enough: their results/phase linger in state, so a later
    // dependency change (e.g. selecting a different roadmap) would re-run this
    // effect with user === null and phase === 'results_ready' and mirror that
    // prior user's data as anonymous. Resetting the view removes that path.
    //
    // answers/profile MUST be cleared here too (DEV-60): they are user-specific and
    // outlive the view. A surviving `profile` is handed to <Roadmap> and posted to
    // /api/roadmap/{id}, so the next account to restore history would have its
    // roadmap personalized with the previous user's experience and projects.
    if (prevUserRef.current && !user) {
      prevUserRef.current = user
      localStorage.removeItem('nextstep_last_recommendations')
      localStorage.removeItem('nextstep_last_career')
      setPhase('idle')
      setResults(null)
      setNotice(null)
      setSelectedCareer(null)
      setActiveTooltip(null)
      setAnswers(null)
      setProfile(null)
      return
    }
    prevUserRef.current = user

    if (user || authLoading) return
    if (phase === 'results_ready' && results) {
      localStorage.setItem('nextstep_last_recommendations', JSON.stringify(results))
      localStorage.setItem('nextstep_last_career', selectedCareer || '')
    } else if (phase === 'idle') {
      localStorage.removeItem('nextstep_last_recommendations')
      localStorage.removeItem('nextstep_last_career')
    }
  }, [phase, results, selectedCareer, user, authLoading])

  const handleStart = () => {
    if (authLoading) return
    if (!user) {
      setAuthModalOpen(true)
      return
    }
    setPhase('assessing')
    scrollTo(assessmentRef)
  }

  // Quiz done -> optional profile step. Answers are parked until it resolves so
  // both reach the matcher in one submit.
  const handleQuizComplete = (quizAnswers) => {
    if (phase === 'loading') return
    runStartedAuthedRef.current = !!localStorage.getItem('nextstep_access_token')
    setAnswers(quizAnswers)
    setPhase('profiling')
    scrollTo(profileRef)
  }

  // `selfProfile` is null when the step was skipped or left empty.
  const handleProfileComplete = async (selfProfile) => {
    // Read LIVE state, not this render's closure. Profile calls back after awaiting
    // its save, by which point a reset may have cleared the run — yet the captured
    // `phase`/`answers` would still read 'profiling' and non-null and let an
    // abandoned assessment submit itself over the reset screen. Doubles as the
    // re-entrancy guard: a second call sees phase==='loading'.
    if (phaseRef.current !== 'profiling' || !answersRef.current) return
    // Checked BEFORE submitting, not after: the harm is the request itself going
    // out unauthenticated and becoming claimable, so catching it afterwards is
    // already too late.
    if (runStartedAuthedRef.current && !localStorage.getItem('nextstep_access_token')) return
    const quizAnswers = answersRef.current
    const runId = runIdRef.current
    setPhase('loading')
    setNotice(null)
    // The profile section unmounts at phase==='loading' and the only LoadingScreen
    // lives in the Assessment section ABOVE it, so without this the user sits at a
    // hole where the form was — with History or blank space below — for the several
    // seconds the match takes. Scroll to the existing loader rather than adding a
    // second one.
    scrollTo(assessmentRef)

    let recs
    let nextNotice
    try {
      recs = await submitQuestionnaire(quizAnswers, selfProfile)
      nextNotice = recs.length === 0 ? 'empty' : null
    } catch (err) {
      console.warn('Falling back to local results:', err)
      // The offline matcher only knows the questionnaire - it has no profile path.
      recs = computeResults(quizAnswers)
      nextNotice = 'offline'
    }

    // A match runs several seconds. If the user signed out or reset in that time,
    // BOTH branches must be dropped: writing them would restore the departed run's
    // results and profile into whatever session is on screen now — and, because the
    // history-restore effect only acts while idle, would then block the next
    // account's own restore and hand it the previous user's profile.
    if (runIdRef.current !== runId) return

    // `profile` is published together with the results it produced, never before.
    // Setting it up front changed Roadmap's personalization inputs while
    // missingSkills still belonged to the PREVIOUS run, firing an LLM roadmap
    // request with mixed inputs that a second request immediately superseded.
    setResults(recs)
    setProfile(selfProfile)
    setNotice(nextNotice)
    setPhase('results_ready')
    scrollTo(resultsRef)
  }

  const handleSelectCareer = (careerId) => {
    setSelectedCareer(careerId)
    setActiveTooltip(null)
    selectCareer(careerId)
    scrollTo(roadmapRef)
  }

  // `profileSnapshot` is the profile that produced these recommendations, stored
  // with the submission. Restoring it (rather than leaving whatever the current run
  // set) keeps the roadmap's personalization consistent with the skill gaps it is
  // shown beside. Defaults to null so an older submission — or the anonymous
  // localStorage path, which has no snapshot — clears it instead of borrowing.
  const handleLoadHistory = (recommendations, careerId = null, profileSnapshot = null) => {
    setResults(recommendations)
    setNotice(null)
    setSelectedCareer(careerId)
    setActiveTooltip(null)
    setProfile(profileSnapshot)
    setPhase('results_ready')
    scrollTo(resultsRef)
  }

  const handleReset = () => {
    // Abandons any in-flight submit/restore so it can't repopulate the view the
    // user just cleared (sign-out is covered by the runIdRef effect on `user`).
    runIdRef.current += 1
    setPhase('idle')
    setResults(null)
    setNotice(null)
    setSelectedCareer(null)
    setActiveTooltip(null)
    setAnswers(null)
    setProfile(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="min-h-screen bg-cream">
      <Header phase={phase} onReset={handleReset} onOpenAuth={() => setAuthModalOpen(true)} />
      <AuthModal open={authModalOpen} onClose={() => setAuthModalOpen(false)} />
      <main>
        <Hero onStart={handleStart} />
        <HowItWorks />
        <div ref={assessmentRef}>
          <Assessment
            phase={phase}
            onStart={handleStart}
            onComplete={handleQuizComplete}
          />
        </div>
        <div ref={profileRef}>
          <Profile
            phase={phase}
            onComplete={handleProfileComplete}
            onSkip={() => handleProfileComplete(null)}
          />
        </div>
        <div ref={resultsRef}>
          <Results
            phase={phase}
            results={results}
            notice={notice}
            onRetry={handleStart}
            onSelectCareer={handleSelectCareer}
            selectedCareer={selectedCareer}
          />
        </div>
        <div ref={roadmapRef}>
          <Roadmap
            selectedCareer={selectedCareer}
            missingSkills={results?.find((r) => r.id === selectedCareer)?.missing_skills ?? []}
            matchedSkills={results?.find((r) => r.id === selectedCareer)?.matched_skills ?? []}
            profile={profile}
            activeTooltip={activeTooltip}
            setActiveTooltip={setActiveTooltip}
          />
        </div>
        <div ref={historyRef}>
          <History user={user} onLoadResults={handleLoadHistory} />
        </div>
      </main>
      <Footer onReset={handleReset} />
    </div>
  )
}

export default App
