import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getWatchlist, removeFromWatchlist, refreshPricesBulk } from '../lib/api'
import toast from 'react-hot-toast'

export default function Watchlist() {
  const navigate = useNavigate()
  const [watchlist, setWatchlist] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshingPrices, setRefreshingPrices] = useState(false)

  useEffect(() => { loadWatchlist() }, [])

  const loadWatchlist = async () => {
    setLoading(true)
    try {
      const res = await getWatchlist()
      setWatchlist(res.data || [])
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const handleRemove = async (companyId, e) => {
    e.stopPropagation()
    try {
      await removeFromWatchlist(companyId)
      setWatchlist(prev => prev.filter(w => w.company_id !== companyId))
      toast.success('Removed from watchlist')
    } catch { toast.error('Failed to remove') }
  }

  if (loading) return <div style={{padding: '24px'}}>Loading...</div>

  return (
    <div className="view active">
      <div className="page-title" style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
        Watchlist
        {watchlist.length > 0 && (
          <button
            className="btn-outline"
            style={{padding:'6px 14px', fontSize:'12px', borderRadius:'6px'}}
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
            {refreshingPrices ? '↻ Refreshing...' : '🔄 Refresh Prices'}
          </button>
        )}
      </div>
      <div className="page-sub">Track companies you're researching.</div>
      
      {watchlist.length === 0 ? (
        <div style={{padding: '40px', textAlign: 'center', color: 'var(--muted)'}}>
          Your watchlist is empty. Search for a company to add it.
        </div>
      ) : (
        <div className="grid-4">
          {watchlist.map(item => {
            const c = item.companies
            const pChange = c.fundamentals_cache?.pChange
            const pChangeText = pChange != null ? (pChange > 0 ? `+${pChange}%` : `${pChange}%`) : ''
            const pChangeColor = pChange > 0 ? 'var(--green)' : (pChange < 0 ? 'var(--red)' : 'var(--muted)')
            
            return (
              <div key={item.id} className="card" style={{cursor:'pointer'}} onClick={() => navigate(`/company/${c.id}`)}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'12px'}}>
                  <div style={{fontWeight:700}}>{c.name}</div>
                  <button 
                    onClick={(e) => handleRemove(c.id, e)}
                    style={{background:'transparent', border:'none', color:'var(--muted)', cursor:'pointer'}}
                  >
                    ×
                  </button>
                </div>
                <div style={{fontFamily:'var(--mono)',fontSize:'20px',marginBottom:'4px'}}>
                  ₹{c.fundamentals_cache?.current_price || '--'}
                  {pChangeText && <span style={{ fontSize: '13px', marginLeft: '10px', color: pChangeColor }}>{pChangeText}</span>}
                </div>
                <div style={{fontSize:'11px',color:'var(--muted)',marginBottom:'12px'}}>{c.exchange}: {c.ticker}</div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
