import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import ChatWidget from './components/ChatWidget'
import { AuthProvider } from './contexts/AuthContext'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
      <ChatWidget />
    </AuthProvider>
  </React.StrictMode>,
)

