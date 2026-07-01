import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'

export default function Sidebar() {
  const { signOut } = useAuth()

  return (
    <aside className="sidebar">
      <div className="logo">
        <div className="logo-mark">
          <div className="logo-icon">📈</div>
          <div>
            <div className="logo-text">StockSense</div>
            <div className="logo-sub">Research Workspace</div>
          </div>
        </div>
      </div>

      <nav className="nav">
        <div className="nav-section">Workspace</div>
        <NavLink to="/" end className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <span className="nav-icon">⊞</span> Dashboard
        </NavLink>
        <NavLink to="/watchlist" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <span className="nav-icon">★</span> Watchlist
        </NavLink>

        <div className="nav-section">My Research</div>
        <NavLink to="/journal" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <span className="nav-icon">📓</span> Decision Journal
        </NavLink>
        <NavLink to="/review" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <span className="nav-icon">🔍</span> Thesis Review
        </NavLink>
      </nav>

      <div className="sidebar-bottom">
        <div className="user-card" onClick={signOut}>
          <div className="avatar">SO</div>
          <div>
            <div className="user-name">Sign Out</div>
            <div className="user-plan">Click to logout</div>
          </div>
        </div>
      </div>
    </aside>
  )
}
