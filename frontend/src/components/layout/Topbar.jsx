import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchCompanies, getWatchlist } from '../../lib/api'
import { Search, Menu } from 'lucide-react'

export default function Topbar({ onMenuClick = () => {} }) {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [showSearch, setShowSearch] = useState(false)
  const [tickerItems, setTickerItems] = useState([])

  const handleSearch = async (q) => {
    setSearchQuery(q)
    if (q.length < 2) {
      setSearchResults([])
      return
    }
    try {
      const res = await searchCompanies(q)
      setSearchResults(res.data || [])
    } catch {
      setSearchResults([])
    }
  }

  // Populate the ticker tape from the user's watchlist (falls back to nothing if empty)
  useEffect(() => {
    let cancelled = false
    getWatchlist()
      .then((res) => {
        if (cancelled) return
        const items = (res.data || [])
          .filter((w) => w.companies?.fundamentals_cache?.current_price != null)
          .map((w) => ({
            ticker: w.companies.ticker,
            price: w.companies.fundamentals_cache.current_price,
            pChange: w.companies.fundamentals_cache.pChange,
          }))
        setTickerItems(items)
      })
      .catch(() => setTickerItems([]))
    return () => { cancelled = true }
  }, [])

  return (
    <header className="topbar">
      <button className="mobile-menu-btn" onClick={onMenuClick} aria-label="Open menu">
        <Menu size={18} />
      </button>

      <div className="search-wrap">
        <span className="search-icon"><Search size={15} /></span>
        <input 
          className="search-input" 
          type="text" 
          placeholder="Search companies — Tata Motors, Infosys, HDFC..." 
          value={searchQuery}
          onChange={(e) => handleSearch(e.target.value)}
          onFocus={() => setShowSearch(true)}
          onBlur={() => setTimeout(() => setShowSearch(false), 200)}
        />
        {showSearch && searchResults.length > 0 && (
          <div className="search-dropdown">
            {searchResults.map((company) => (
              <div 
                key={company.id}
                className="search-dropdown-item"
                onMouseDown={() => {
                  navigate(`/company/${company.id}`)
                  setSearchQuery('')
                  setSearchResults([])
                }}
              >
                <span className="search-dropdown-ticker">{company.ticker}</span>
                <span className="search-dropdown-name">{company.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="topbar-right">
        {tickerItems.length > 0 && (
          <div className="ticker-tape">
            <div className="ticker-track">
              {[...tickerItems, ...tickerItems].map((t, i) => (
                <span className="ticker-item" key={i}>
                  <span className="ticker-symbol">{t.ticker}</span>
                  <span className={t.pChange > 0 ? 'up' : t.pChange < 0 ? 'down' : ''}>
                    {t.pChange != null ? `${t.pChange > 0 ? '+' : ''}${t.pChange}%` : '—'}
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}
        <div className="market-pill"><div className="dot"></div> NIFTY 50 <span className="up">▲ 22,847 +0.6%</span></div>
        <div className="market-pill">SENSEX <span className="down">▼ 75,312 −0.2%</span></div>
      </div>
    </header>
  )
}
