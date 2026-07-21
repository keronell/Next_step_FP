// Minimal dependency-free path router. The app is otherwise a single-page phase
// machine (no react-router); this adds just enough to give the roadmap its own
// addressable URL (DEV-65's `/roadmap/{id}` intent) so a returning user can deep-
// link straight to it (DEV-76), while every other path renders the scroll app.
//
// navigate() drives programmatic pushes; the browser Back button is handled via
// the native `popstate`. Both funnel through a private `nextstep:navigate` event
// so every useRoute() consumer re-renders on a same-tab push (pushState alone
// fires no event).
import { useEffect, useState } from 'react'

const NAV_EVENT = 'nextstep:navigate'

// Programmatic navigation: push the URL, scroll to top, notify consumers.
export function navigate(path) {
  if (path === currentPath()) return
  window.history.pushState({}, '', path)
  window.scrollTo(0, 0)
  window.dispatchEvent(new Event(NAV_EVENT))
}

function currentPath() {
  return window.location.pathname
}

// Returns the `careerId` for `/roadmap/:careerId`, else null. Trailing slashes
// and empty segments are treated as "no match". A malformed percent-encoded
// segment (e.g. `/roadmap/%E0%A4%A`) would make decodeURIComponent throw during
// render and blank the whole app, so decode failures are treated as "no match"
// too — the path just falls through to the normal scroll app.
export function matchRoadmap(pathname) {
  const m = pathname.match(/^\/roadmap\/([^/]+)\/?$/)
  if (!m) return null
  try {
    return decodeURIComponent(m[1])
  } catch {
    return null
  }
}

// Subscribe to the current pathname, re-rendering on Back/forward (popstate) and
// on programmatic navigate() (NAV_EVENT).
export function useRoute() {
  const [path, setPath] = useState(currentPath())

  useEffect(() => {
    const onChange = () => setPath(currentPath())
    window.addEventListener('popstate', onChange)
    window.addEventListener(NAV_EVENT, onChange)
    return () => {
      window.removeEventListener('popstate', onChange)
      window.removeEventListener(NAV_EVENT, onChange)
    }
  }, [])

  return path
}
