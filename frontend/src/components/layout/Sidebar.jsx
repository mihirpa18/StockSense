import { NavLink } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { TrendingUp, LayoutDashboard, Star, NotebookText, Target, LogOut, X } from 'lucide-react'

export default function Sidebar({ isOpen = false, onClose = () => {} }) {
  const { signOut } = useAuth()

  return (
    <>
      <div className={`sidebar-overlay ${isOpen ? 'visible' : ''}`} onClick={onClose} />
      <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
        <div className="logo">
          <div className="logo-mark">
            <div className="logo-icon"><TrendingUp size={17} strokeWidth={2.5} /></div>
            <div>
              <div className="logo-text">StockSense</div>
              <div className="logo-sub">Research Workspace</div>
            </div>
            <button className="sidebar-close" onClick={onClose} aria-label="Close menu">
              <X size={15} />
            </button>
          </div>
        </div>

        <nav className="nav">
          <div className="nav-section">Workspace</div>
          <NavLink to="/" end onClick={onClose} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon"><LayoutDashboard size={16} /></span> Dashboard
          </NavLink>
          <NavLink to="/watchlist" onClick={onClose} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon"><Star size={16} /></span> Watchlist
          </NavLink>

          <div className="nav-section">My Research</div>
          <NavLink to="/journal" onClick={onClose} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon"><NotebookText size={16} /></span> Decision Journal
          </NavLink>
          <NavLink to="/review" onClick={onClose} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon"><Target size={16} /></span> Thesis Review
          </NavLink>
        </nav>

        <div className="sidebar-bottom">
          <div className="user-card" onClick={signOut}>
            <div className="avatar"><LogOut size={14} /></div>
            <div>
              <div className="user-name">Sign Out</div>
              <div className="user-plan">Click to logout</div>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}
