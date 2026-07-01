import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getWatchlist, getJournalEntries, refreshPricesBulk } from '../lib/api'
import { supabase } from '../lib/supabase'
import { useAuth } from '../hooks/useAuth'
import toast from 'react-hot-toast'

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [watchlist, setWatchlist] = useState([])
  const [recentJournal, setRecentJournal] = useState([])
  const [thesisCount, setThesisCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [refreshingPrices, setRefreshingPrices] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [watchRes, journalRes] = await Promise.all([
        getWatchlist(),
        getJournalEntries()
      ])
      setWatchlist(watchRes.data || [])
      setRecentJournal((journalRes.data || []).slice(0, 3))

      const { count } = await supabase
        .from('theses')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', user?.id)
      setThesisCount(count || 0)
    } catch (err) {
      console.error('Dashboard load error:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', gap: '20px', flexDirection: 'column' }}>
        <div>Loading dashboard...</div>
      </div>
    )
  }

  return (
    <div className="view active">
      <div className="page-title">Good morning{user?.user_metadata?.full_name ? `, ${user.user_metadata.full_name.split(' ')[0]}` : ''} 👋</div>
      <div className="page-sub">You have {thesisCount} active theses.</div>

      <div className="grid-3">
        <div className="card">
          <div className="card-label">Watchlist</div>
          <div className="card-value up">{watchlist.length}</div>
          <div className="card-change up">Companies tracking</div>
          <div className="card-desc">Your curated list of interesting stocks</div>
        </div>
        <div className="card">
          <div className="card-label">Active Theses</div>
          <div className="card-value" style={{color: 'var(--accent)'}}>{thesisCount}</div>
          <div className="card-change">Building conviction</div>
          <div className="card-desc">Based on latest uploaded reports</div>
        </div>
        <div className="card">
          <div className="card-label">Journal Entries</div>
          <div className="card-value" style={{color: 'var(--green)'}}>{recentJournal.length}</div>
          <div className="card-change">Decisions logged</div>
          <div className="card-desc">Reflecting on your investment choices</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="section-title" style={{justifyContent:'space-between'}}>
            <span>Watchlist <span style={{fontWeight:400,color:'var(--muted)'}}>{watchlist.length} companies</span></span>
            {watchlist.length > 0 && (
              <button
                className="btn-outline"
                style={{padding:'4px 12px', fontSize:'11px', borderRadius:'6px'}}
                disabled={refreshingPrices}
                onClick={async () => {
                  setRefreshingPrices(true)
                  try {
                    const ids = watchlist.map(w => w.companies.id)
                    const res = await refreshPricesBulk(ids)
                    const updated = res.data
                    setWatchlist(prev => prev.map(w => {
                      const freshCache = updated[w.companies.id]
                      if (freshCache) {
                        return { ...w, companies: { ...w.companies, fundamentals_cache: freshCache } }
                      }
                      return w
                    }))
                    toast.success('Prices refreshed')
                  } catch {
                    toast.error('Price refresh failed')
                  } finally {
                    setRefreshingPrices(false)
                  }
                }}
              >
                {refreshingPrices ? '↻ ...' : '🔄 Refresh Prices'}
              </button>
            )}
          </div>
          {watchlist.slice(0, 4).map((item) => {
            const company = item.companies
            const pChange = company.fundamentals_cache?.pChange
            const pChangeText = pChange != null ? (pChange > 0 ? `+${pChange}%` : `${pChange}%`) : ''
            const pChangeColor = pChange > 0 ? 'var(--green)' : (pChange < 0 ? 'var(--red)' : 'var(--muted)')
            
            // Placeholder random values since we don't fetch all data for watchlist on dashboard
            return (
              <div key={item.id} className="watchlist-row" onClick={() => navigate(`/company/${company.id}`)}>
                <div>
                  <div className="stock-name">{company.name}</div>
                  <div className="stock-sector">{company.sector || 'Various'} · {company.exchange}: {company.ticker}</div>
                </div>
                <div className="stock-price">
                  <div className="price-val">₹{company.fundamentals_cache?.current_price || '--'}</div>
                  <div className="price-chg" style={{ color: pChangeColor }}>{pChangeText}</div>
                </div>
              </div>
            )
          })}
          {watchlist.length === 0 && <div style={{padding: '20px 0', color: 'var(--muted)', fontSize: '13px'}}>Your watchlist is empty.</div>}
        </div>

        <div className="card">
          <div className="section-title">Recent Activity</div>
          <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
            {recentJournal.map(entry => (
              <div key={entry.id} style={{display:'flex',gap:'12px',alignItems:'flex-start'}}>
                <div style={{width:'32px',height:'32px',borderRadius:'8px',background:'rgba(139,92,246,0.15)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:'14px',flexShrink:0}}>📓</div>
                <div>
                  <div style={{fontSize:'13px',fontWeight:500}}>Journal entry — {entry.action} {entry.stock_name}</div>
                  <div style={{fontSize:'11px',color:'var(--muted)',marginTop:'2px'}}>{new Date(entry.purchase_date).toLocaleDateString()} · ₹{entry.price} entry price</div>
                </div>
              </div>
            ))}
            {recentJournal.length === 0 && <div style={{color: 'var(--muted)', fontSize: '13px'}}>No recent activity.</div>}
          </div>
        </div>
      </div>
    </div>
  )
}
