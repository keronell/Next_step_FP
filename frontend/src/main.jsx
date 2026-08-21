import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { AuthProvider } from './contexts/AuthContext'
import { bootRedirect } from './hooks/useRoute'
import './index.css'

// DEV-76: decide the returning user's destination before the first render, so the
// roadmap is simply where the app opens rather than somewhere it moves them to a
// moment later. Must run above createRoot — after it, there is a rendered homepage
// to flash and a user who may already be interacting with it.
bootRedirect()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>,
)

