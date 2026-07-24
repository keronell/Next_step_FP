import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Send, Sparkles, X } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { streamChatMessage } from '../api'
import { navigate as routeTo, navigateToSection } from '../hooks/useRoute'

// Bottom-left "next step helper" bubble (see CLAUDE.md's chatbot plan). Mounted
// in main.jsx, OUTSIDE <App>, so it survives App's route branching (the
// standalone /roadmap/{id} page is an early return that unmounts everything
// below it) and appears on every page while the user is logged in.
//
// Own outside-click handling, deliberately not reusing Header's — Header's ref-
// based close logic is what several recent commits had to fix (a tap inside the
// panel being swallowed as "outside"); a second, independent implementation
// here can't reintroduce that same class of bug in this component.
const CONNECT_TIMEOUT_MS = 20000

function parseSseChunk(buffer) {
  const parts = buffer.split('\n\n')
  const rest = parts.pop() // last part may be incomplete — kept for the next read
  const events = []
  for (const part of parts) {
    const line = part.trim()
    if (!line.startsWith('data:')) continue
    try {
      events.push(JSON.parse(line.slice(5).trim()))
    } catch {
      // malformed frame — ignore rather than crash the widget
    }
  }
  return { events, rest }
}

export default function ChatWidget() {
  const { user, authLoading } = useAuth()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const conversationIdRef = useRef(null)
  const panelRef = useRef(null)
  const bubbleRef = useRef(null)
  const listRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const onClick = (e) => {
      if (panelRef.current?.contains(e.target) || bubbleRef.current?.contains(e.target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, open])

  if (authLoading || !user) return null

  const applyNavigateAction = (action) => {
    if (action.target === 'questionnaire') {
      navigateToSection('assessment')
    } else if (action.target === 'roadmap' && action.career_id) {
      routeTo(`/roadmap/${encodeURIComponent(action.career_id)}`)
      if (action.step_id) {
        setTimeout(() => {
          document.getElementById(action.step_id)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }, 300)
      }
    }
  }

  const handleSend = async (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || sending) return
    setInput('')
    setSending(true)
    setMessages((prev) => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '' }])

    const controller = new AbortController()
    let connectTimer = setTimeout(() => controller.abort(), CONNECT_TIMEOUT_MS)
    const clearConnectTimer = () => {
      clearTimeout(connectTimer)
      connectTimer = null
    }

    const setLastAssistantContent = (updater) => {
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        next[next.length - 1] = { ...last, content: updater(last.content) }
        return next
      })
    }

    try {
      const body = await streamChatMessage(conversationIdRef.current, text)
      const reader = body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let failed = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        clearConnectTimer()
        buffer += decoder.decode(value, { stream: true })
        const { events, rest } = parseSseChunk(buffer)
        buffer = rest

        for (const evt of events) {
          if (evt.conversation_id) conversationIdRef.current = evt.conversation_id
          else if (evt.token) setLastAssistantContent((c) => c + evt.token)
          else if (evt.action === 'navigate') applyNavigateAction(evt)
          else if (evt.error) {
            failed = true
            setLastAssistantContent(() => evt.error)
          }
        }
      }
      if (!failed) {
        // nothing further to do — content already streamed in
      }
    } catch {
      clearConnectTimer()
      setLastAssistantContent(() => 'The assistant is unavailable right now.')
    } finally {
      clearConnectTimer()
      setSending(false)
    }
  }

  return (
    <div className="fixed bottom-6 left-6 z-50">
      <AnimatePresence>
        {open && (
          <motion.div
            ref={panelRef}
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.96 }}
            transition={{ duration: 0.18 }}
            className="mb-3 flex h-[28rem] w-[22rem] max-w-[calc(100vw-3rem)] flex-col overflow-hidden rounded-2xl border border-navy/[0.08] bg-white shadow-lg"
          >
            <div className="flex items-center justify-between border-b border-navy/[0.08] bg-cream/60 px-4 py-3">
              <div className="flex items-center gap-2 text-navy">
                <Sparkles size={16} className="text-gold" aria-hidden="true" />
                <span className="text-small font-semibold">Next Step Helper</span>
              </div>
              <button
                type="button"
                className="focus-ring rounded-md p-1 text-navy/60 hover:text-navy"
                onClick={() => setOpen(false)}
                aria-label="Close chat"
              >
                <X size={16} />
              </button>
            </div>

            <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
              {messages.length === 0 && (
                <p className="text-small text-ink-soft">
                  Ask me about your roadmap, your next step, or the assessment.
                </p>
              )}
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={
                    m.role === 'user'
                      ? 'ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-navy px-3 py-2 text-small text-white'
                      : 'mr-auto max-w-[85%] rounded-2xl rounded-bl-sm bg-cream px-3 py-2 text-small text-navy'
                  }
                >
                  {m.content || (sending && i === messages.length - 1 ? '…' : '')}
                </div>
              ))}
            </div>

            <form onSubmit={handleSend} className="flex items-center gap-2 border-t border-navy/[0.08] p-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about your roadmap…"
                className="focus-ring flex-1 rounded-full border border-navy/[0.12] bg-cream/40 px-3 py-2 text-small text-navy placeholder:text-ink-soft"
                disabled={sending}
              />
              <button
                type="submit"
                className="focus-ring flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gold text-navy disabled:opacity-50"
                disabled={sending || !input.trim()}
                aria-label="Send"
              >
                <Send size={15} />
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button
        ref={bubbleRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        whileHover={{ y: -2 }}
        whileTap={{ scale: 0.95 }}
        className="focus-ring flex h-14 w-14 items-center justify-center rounded-full bg-navy text-gold shadow-lg"
        aria-label="Next Step Helper"
      >
        {open ? <X size={22} /> : <Sparkles size={22} />}
      </motion.button>
    </div>
  )
}
