import { useEffect, useRef, useState } from 'react'
import Header from './components/Header'
import Footer from './components/Footer'
import Hero from './pages/Landing'
import HowItWorks from './pages/HowItWorks'
import Assessment from './pages/Questionnaire'
import Profile from './pages/Profile'
import Results from './pages/Results'
import AuthModal from './pages/AuthModal'
import RoadmapPage from './pages/RoadmapPage'
import Admin from './pages/Admin'
import { computeResults } from './data'
import { submitQuestionnaire, selectCareer, fetchMySubmissions } from './api'
import { useAuth } from './contexts/AuthContext'
import { useRoute, matchRoadmap, navigate, navigateToSection, consumePendingScroll, replaceWithHome, didBootJump } from './hooks/useRoute'
import { resumeCareerFrom, setResumeCareer } from './lib/resume'

function App() {
  const { user, authLoading } = useAuth()

  // Deep-link routing: `/roadmap/{id}` renders the standalone roadmap (bypassing
  // the intro/questionnaire); every other path renders the scroll app below.
  const path = useRoute()
  const roadmapCareerId = matchRoadmap(path)
  // DEV-62 admin screen. Like the roadmap route it replaces the scroll app, so it
  // is subject to the same mid-run guard below.
  const adminRoute = path === '/admin'

  const [phase, setPhase] = useState('idle')
  const [results, setResults] = useState(null)
  const [notice, setNotice] = useState(null)
  const [selectedCareer, setSelectedCareer] = useState(null)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  // The career whose roadmap a returning user can jump straight to (their most
  // recent completed assessment). Drives the header's "My Roadmap" shortcut; null
  // for users with no completed assessment, so their flow stays untouched.
  const [resumeCareerId, setResumeCareerId] = useState(null)

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
          // The effect's own `phase === 'idle'` test was evaluated before this fetch;
          // re-read it LIVE. The run token doesn't cover this: handleGoToAssessment
          // bumps it, but handleStart — what the Hero CTA calls — does not, so a user
          // who starts an assessment from the hero while the restore is still in
          // flight would have it clobbered back to results_ready, and (since DEV-76)
          // be navigated off to an old roadmap on top of that.
          if (phaseRef.current !== 'idle') return
          // An empty history must ERASE the pointer, not merely skip updating it.
          // This is the backstop for staleness we can't observe locally — the
          // submissions deleted in another tab, on another device, or by an admin.
          // Without it a pointer can outlive every submission behind it and boot
          // this browser onto a locked roadmap on every future visit.
          if (!subs?.length) {
            setResumeCareer(null)
            return
          }
          const latest = [...subs].sort(
            (a, b) => new Date(b.created_at) - new Date(a.created_at),
          )[0]
          // DEV-76: this restore no longer routes anywhere. It records the resume
          // career (below), and the NEXT page load acts on it in bootRedirect(),
          // before rendering. Navigating from here is what forced five guards: by
          // the time this resolves, auth has re-run, effects have replayed and the
          // user has had hundreds of milliseconds to go somewhere of their own.
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
    // outlive the view. A surviving `profile` rides the next submitQuestionnaire()
    // into the matcher, so the next account on this browser would be scored against
    // the previous user's experience and projects.
    if (prevUserRef.current && !user) {
      prevUserRef.current = user
      localStorage.removeItem('nextstep_last_recommendations')
      localStorage.removeItem('nextstep_last_career')
      // The resume pointer is cleared by the auth-settled effect above, which covers
      // this sign-out AND the expired-token case this branch cannot see.
      setPhase('idle')
      setResults(null)
      setNotice(null)
      setSelectedCareer(null)
      setAnswers(null)
      setProfile(null)
      setResumeCareerId(null)
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

  // Remember which roadmap a signed-in user is on, for bootRedirect() to act on at
  // the START of the next visit. Writing it is the whole cost of the feature; the
  // reading side is three synchronous localStorage/URL checks with no window to
  // defend. Deliberately NOT written for anonymous users — the boot redirect
  // requires a token, and the sign-out cleanup below clears the key so the next
  // account on this browser cannot inherit it.
  useEffect(() => {
    if (user && resumeCareerId) setResumeCareer(resumeCareerId)
  }, [user, resumeCareerId])

  // Auth has settled and there is nobody signed in. Two jobs, both consequences of
  // bootRedirect() trusting a token's PRESENCE — validating it would cost the very
  // request whose window this design removes.
  //
  // 1. Drop the pointer. It belongs to a session that no longer exists, and it is
  //    NOT enough to clear it on sign-out: a token that expires between visits is
  //    discovered only when getMe() rejects, so `user` is never truthy, which means
  //    `prevUserRef.current` is null and the sign-out branch below never runs. The
  //    pointer would then survive into the next account to sign in on this browser
  //    and send their first load to the previous account's career.
  // 2. If we already routed on that pointer, go home — otherwise the visit ends on a
  //    roadmap RoadmapPage correctly walls off as signed-out.
  useEffect(() => {
    if (authLoading || user) return
    setResumeCareer(null)
    if (didBootJump()) replaceWithHome()
  }, [authLoading, user])

  // Returning to the scroll app from a route (e.g. the roadmap page) may carry a
  // deferred section target: a nav control clicked while its section wasn't mounted
  // (see navigateToSection). Honor it once we're back on the scroll app, giving the
  // sections a tick to mount/lay out before scrolling.
  useEffect(() => {
    if (roadmapCareerId) return
    const id = consumePendingScroll()
    if (!id) return
    const t = setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 80)
    return () => clearTimeout(t)
  }, [roadmapCareerId])

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
    // "My Roadmap" shortcut (DEV-76). Set here, AFTER the abandoned-run guard
    // above — pointing it at a run the user walked away from is the same class
    // of bug that guard exists to prevent.
    setResumeCareerId(recs?.[0]?.id ?? null)
    setProfile(selfProfile)
    setNotice(nextNotice)
    setPhase('results_ready')
    scrollTo(resultsRef)
  }

  const handleSelectCareer = (careerId) => {
    // The roadmap lives on its own page now (no inline section on the front page):
    // open it there. Record the selection HERE, on the explicit result click —
    // not on the roadmap page's mount, so merely opening a bookmark can't record a
    // selection (which is session-scoped and could clobber another account's).
    // Set selectedCareer too (not just the resume id) so returning via the Back
    // button shows the card as selected, and the anonymous-persistence effect
    // mirrors the right nextstep_last_career for a later reload.
    setSelectedCareer(careerId)
    setResumeCareerId(careerId)
    selectCareer(careerId)
    navigate(`/roadmap/${encodeURIComponent(careerId)}`)
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
    setProfile(profileSnapshot)
    // The "My Roadmap" shortcut points at the selected career, else the top match.
    // Returned as well as stored: callers that need to ROUTE to it can't read it back
    // out of state on this tick, and both of them had reimplemented the rule inline.
    const resumeCareer = careerId ?? recommendations?.[0]?.id ?? null
    setResumeCareerId(resumeCareer)
    setPhase('results_ready')
    scrollTo(resultsRef)
    return resumeCareer
  }

  // History now lives on the standalone roadmap page (moved off the scroll app),
  // so loading a past assessment from there must also route to the career it
  // belongs to — plain handleLoadHistory only updates in-memory state, which the
  // roadmap route ignores unless it already matches the URL's careerId (see
  // roadmapUsesCurrentRun below). navigate() no-ops if we're already there.
  // DEV-75 deletes a past assessment; DEV-76 caches which one to resume to. Deleting
  // the submission a pointer came from must therefore recompute it — from the list
  // the delete already refetched, so there is no extra request and no chance of
  // reading back a not-yet-consistent history. Recompute rather than clear: deleting
  // one of several assessments should resume to the newest survivor, not nothing.
  //
  // App owns this rather than History writing the key itself, so the in-memory
  // `resumeCareerId` and the stored pointer cannot disagree — a split would let the
  // write effect above resurrect a deleted career on the next render.
  const handleHistoryChanged = (freshSubs) => {
    const next = resumeCareerFrom(freshSubs)
    setResumeCareerId(next)
    setResumeCareer(next)
  }

  const handleLoadHistoryOnRoadmap = (recommendations, careerId = null, profileSnapshot = null) => {
    const targetCareer = handleLoadHistory(recommendations, careerId, profileSnapshot)
    if (targetCareer) navigate(`/roadmap/${encodeURIComponent(targetCareer)}`)
  }

  const handleReset = () => {
    // Abandons any in-flight submit/restore so it can't repopulate the view the
    // user just cleared (sign-out is covered by the runIdRef effect on `user`).
    runIdRef.current += 1
    setPhase('idle')
    setResults(null)
    setNotice(null)
    setSelectedCareer(null)
    setAnswers(null)
    setProfile(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Header's Assessment / Start Assessment controls. Questionnaire renders nothing
  // while phase is 'results_ready', so a returning user (whose background restore
  // set that phase, e.g. while the standalone roadmap page was showing) would land
  // on a blank assessment section. Reset to the idle start card first — but never
  // disturb an in-progress assessment. navigateToSection scrolls here, or routes
  // home and defers the scroll when we're on the roadmap route.
  const handleGoToAssessment = () => {
    // 'profiling' is an ACTIVE phase too (DEV-60). main's guard predates it, so
    // resetting from there unmounted the profile form and discarded its
    // component-local edits — taking the parked quiz answers with it.
    const inProgress = phase === 'assessing' || phase === 'profiling' || phase === 'loading'
    if (!inProgress) {
      // Also invalidates a pending restore. fetchMySubmissions() can still be in
      // flight from mount, and its continuation calls handleLoadHistory — which
      // would flip us to results_ready over the assessment the user just explicitly
      // asked for. Bumping the run token is what the restore guard already checks.
      runIdRef.current += 1
      setPhase('idle')
      setResults(null)
      setNotice(null)
      setSelectedCareer(null)
    }
    // Send them where they actually are: the assessment section renders nothing
    // while profiling, so scrolling there would look like the flow vanished.
    navigateToSection(phase === 'profiling' ? 'profile' : 'assessment')
  }

  // Is there live component-local state a route change would destroy? Questionnaire
  // holds the quiz answers ('assessing') and Profile the unsaved form edits
  // ('profiling'); both live in the children, and the roadmap route below is an
  // EXCLUSIVE branch that unmounts them. 'loading' is absent on purpose — by then
  // the answers are parked in App, which stays mounted either way. Same predicate
  // Header uses to hide the "My Roadmap" shortcut.
  const midRun = phase === 'assessing' || phase === 'profiling'

  // Because Header hides both that shortcut and the Admin link mid-run, nothing in
  // the app can navigate to the roadmap or /admin mid-run — so an arrival at either
  // during one is always the browser's Back or Forward landing on an entry left over
  // from earlier in the session (the user opened a roadmap, came back, and started a
  // new assessment). Honoring it would unmount the quiz and remount it empty on the
  // way back, silently restarting it. Refuse the entry instead: keep rendering the
  // scroll app, then rewrite that entry to home so a second press can't walk in again.
  //
  // Keyed on the run rather than on history bookkeeping, which is what makes it
  // survive a reload: a reload destroys the run and any module-level marker
  // together, so there is never a live run stranded on the far side of one.
  useEffect(() => {
    if (!midRun || (!roadmapCareerId && !adminRoute)) return
    replaceWithHome()
    // Refusing the entry doesn't undo the traversal's scroll restoration: the
    // browser already put us at the roadmap entry's saved offset, on a document
    // that never changed. Without this the run survives but sits off-screen, so
    // Back reads as "dropped me in a random section". scrollTo's defer also keeps
    // us behind that restore rather than racing it.
    scrollTo(phase === 'profiling' ? profileRef : assessmentRef)
  }, [roadmapCareerId, adminRoute, midRun])

  // Does the app's in-memory run describe THIS career? Two ways it can:
  //   selectedCareer — the user explicitly clicked "View Roadmap" on that card
  //   resumeCareerId — it is the current run's headline match, which is exactly
  //                    what the header's "My Roadmap" shortcut opens
  // The second matters because selectedCareer stays null after a plain submit (and
  // after loading a history item with no selection), and submission persistence is
  // async — so withholding here would send a just-finished assessment to the history
  // fallback, which may not have it yet, yielding a generic or older roadmap.
  // When NEITHER matches we withhold on purpose: on a deep link the background
  // restore may hold a different assessment that merely contains this career.
  const roadmapUsesCurrentRun =
    roadmapCareerId != null &&
    (selectedCareer === roadmapCareerId || resumeCareerId === roadmapCareerId)

  // Standalone roadmap route (DEV-76/DEV-65): render only the roadmap, skipping
  // the whole intro/questionnaire flow the scroll app renders below. Hand the page
  // the current results so a just-clicked "View Roadmap" uses that recommendation
  // directly, rather than re-fetching a not-yet-persisted submission from history.
  // Admin route (DEV-62). Admin.jsx does its own role check — it waits for
  // authLoading to resolve before bouncing a non-admin home.
  if (adminRoute && !midRun) return <Admin />

  if (roadmapCareerId && !midRun) {
    return (
      <RoadmapPage
        careerId={roadmapCareerId}
        recommendations={roadmapUsesCurrentRun ? results : null}
        onStartAssessment={handleGoToAssessment}
        onLoadResults={handleLoadHistoryOnRoadmap}
        onHistoryChanged={handleHistoryChanged}
      />
    )
  }

  return (
    <div className="min-h-screen bg-cream">
      <Header
        phase={phase}
        onReset={handleReset}
        onOpenAuth={() => setAuthModalOpen(true)}
        onStartAssessment={handleGoToAssessment}
        roadmapCareerId={resumeCareerId}
      />
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
      </main>
      <Footer onReset={handleReset} onStartAssessment={handleGoToAssessment} />
    </div>
  )
}

export default App
