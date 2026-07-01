import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useNavigate } from 'react-router-dom'
import { LiquidBackground } from '../components/ui/LiquidBackground'
import { TrendingUp, Mail, Lock, User, ArrowRight } from 'lucide-react'
import toast from 'react-hot-toast'

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)
  const { signIn, signUp, user } = useAuth()
  const navigate = useNavigate()

  // Redirect if already logged in
  if (user) {
    navigate('/', { replace: true })
    return null
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)

    try {
      if (isLogin) {
        const { error } = await signIn(email, password)
        if (error) throw error
        toast.success('Welcome back!')
        navigate('/')
      } else {
        const { error } = await signUp(email, password, fullName)
        if (error) throw error
        toast.success('Account created! Check your email to verify.')
      }
    } catch (err) {
      toast.error(err.message || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-container">
      <LiquidBackground />
      
      <div className="auth-card-wrapper">
        {/* Logo */}
        <div className="auth-logo-section">
          <div className="auth-logo-icon">
            <TrendingUp size={24} />
          </div>
          <div>
            <h1 className="auth-logo-title">StockSense</h1>
            <p className="auth-logo-subtitle">AI-Powered Investment Research</p>
          </div>
        </div>
 
        {/* Auth Card */}
        <div className="auth-card">
          <h2 className="auth-card-title">
            {isLogin ? 'Welcome back' : 'Create your account'}
          </h2>
          <p className="auth-card-subtitle">
            {isLogin ? 'Sign in to continue your research' : 'Start making smarter investment decisions'}
          </p>
 
          <form onSubmit={handleSubmit} className="auth-form">
            {!isLogin && (
              <div className="auth-input-group">
                <span className="auth-input-icon">
                  <User size={16} />
                </span>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Full name"
                  className="auth-input"
                  id="auth-fullname"
                />
              </div>
            )}
 
            <div className="auth-input-group">
              <span className="auth-input-icon">
                <Mail size={16} />
              </span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email address"
                required
                className="auth-input"
                id="auth-email"
              />
            </div>
 
            <div className="auth-input-group">
              <span className="auth-input-icon">
                <Lock size={16} />
              </span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                required
                minLength={6}
                className="auth-input"
                id="auth-password"
              />
            </div>
 
            <button
              type="submit"
              disabled={loading}
              className="auth-btn"
              id="auth-submit-btn"
            >
              {loading ? (
                <span className="animate-pulse">Processing...</span>
              ) : (
                <>
                  {isLogin ? 'Sign In' : 'Create Account'}
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>
 
          <div className="auth-toggle-wrapper">
            <button
              onClick={() => setIsLogin(!isLogin)}
              className="auth-toggle-link"
              id="auth-toggle-btn"
            >
              {isLogin ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
            </button>
          </div>
        </div>
 
        <p className="auth-footer">
          Research tool for educational purposes. Not financial advice.
        </p>
      </div>
    </div>
  )
}
