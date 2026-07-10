import { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useAuth } from './hooks/useAuth'
import Sidebar from './components/layout/Sidebar'
import Topbar from './components/layout/Topbar'
import Dashboard from './pages/Dashboard'
import Company from './pages/Company'
import Watchlist from './pages/Watchlist'
import Journal from './pages/Journal'
import ThesisReview from './pages/ThesisReview'
import AuthPage from './pages/Auth'

import { LiquidBackground } from './components/ui/LiquidBackground'

function AppShell({ children }) {
  const [navOpen, setNavOpen] = useState(false)
  return (
    <>
      <LiquidBackground />
      <Sidebar isOpen={navOpen} onClose={() => setNavOpen(false)} />
      <div className="main">
        <Topbar onMenuClick={() => setNavOpen(true)} />
        <div className="content">
          {children}
        </div>
      </div>
    </>
  )
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', width: '100%' }}>Loading...</div>
  if (!user) return <Navigate to="/auth" replace />
  return <AppShell>{children}</AppShell>
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-right" toastOptions={{ style: { background: 'var(--panel)', color: 'var(--text)', border: '1px solid var(--border)' } }} />
      <Routes>
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/company/:id" element={<ProtectedRoute><Company /></ProtectedRoute>} />
        <Route path="/watchlist" element={<ProtectedRoute><Watchlist /></ProtectedRoute>} />
        <Route path="/journal" element={<ProtectedRoute><Journal /></ProtectedRoute>} />
        <Route path="/review" element={<ProtectedRoute><ThesisReview /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  )
}
