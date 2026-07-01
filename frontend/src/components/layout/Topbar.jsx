import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchCompanies } from '../../lib/api'

export default function Topbar() {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [showSearch, setShowSearch] = useState(false)

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

  return (
    <header className="topbar">
      <div className="search-wrap">
        <span className="search-icon">🔍</span>
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
        <div className="market-pill"><div className="dot"></div> NIFTY 50 <span className="up">▲ 22,847 +0.6%</span></div>
        <div className="market-pill">SENSEX <span className="down">▼ 75,312 −0.2%</span></div>
      </div>
    </header>
  )
}
