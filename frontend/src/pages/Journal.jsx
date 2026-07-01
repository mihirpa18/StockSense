import { useEffect, useState } from 'react'
import { saveJournalEntry, getJournalEntries, searchCompanies } from '../lib/api'
import toast from 'react-hot-toast'

const HORIZONS = [
  { label: '6 Months', value: '6M' },
  { label: '1 Year', value: '1Y' },
  { label: '3 Years', value: '3Y' },
  { label: '5 Years', value: '5Y' }
]

const horizonLabels = {
  '6M': '6 Months',
  '1Y': '1 Year',
  '3Y': '3 Years',
  '5Y': '5 Years'
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  const day = String(d.getDate()).padStart(2, '0')
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const year = d.getFullYear()
  return `${day}-${month}-${year}`
}

export default function Journal() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [companySearch, setCompanySearch] = useState('')
  const [companyResults, setCompanyResults] = useState([])
  const [form, setForm] = useState({
    company_id: '', stock_name: '', ticker: '', action: 'BUY',
    price: '', quantity: '', purchase_date: new Date().toISOString().split('T')[0],
    reason: '', risks_identified: '', confidence: 7, horizon: '1Y'
  })

  useEffect(() => { loadEntries() }, [])

  const loadEntries = async () => {
    try {
      const res = await getJournalEntries()
      setEntries(res.data || [])
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const handleCompanySearch = async (q) => {
    setCompanySearch(q)
    if (q.length < 2) { setCompanyResults([]); return }
    try {
      const res = await searchCompanies(q)
      setCompanyResults(res.data || [])
    } catch { setCompanyResults([]) }
  }

  const selectCompany = (c) => {
    setForm(f => ({ ...f, company_id: c.id, stock_name: c.name, ticker: c.ticker }))
    setCompanySearch(c.name)
    setCompanyResults([])
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.company_id || !form.reason || !form.price) {
      toast.error('Fill all required fields'); return
    }
    setSaving(true)
    try {
      await saveJournalEntry({ ...form, price: parseFloat(form.price), quantity: form.quantity ? parseInt(form.quantity) : null })
      toast.success('Entry saved!')
      setForm({ company_id: '', stock_name: '', ticker: '', action: 'BUY', price: '', quantity: '', purchase_date: new Date().toISOString().split('T')[0], reason: '', risks_identified: '', confidence: 7, horizon: '1Y' })
      setCompanySearch('')
      loadEntries()
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed to save') }
    finally { setSaving(false) }
  }

  if (loading) return <div style={{padding: '24px'}}>Loading...</div>

  return (
    <div className="view active">
      <div className="page-title">Decision Journal</div>
      <div className="page-sub">Record your investment decisions. Future you will thank present you.</div>

      <div style={{display:'grid',gridTemplateColumns:'1fr 380px',gap:'20px'}}>
        <div>
          {entries.length === 0 ? (
            <div style={{color:'var(--muted)', textAlign:'center', padding:'40px'}}>No entries yet.</div>
          ) : (
            entries.map(entry => (
              <div key={entry.id} className="journal-entry">
                <div className="journal-header">
                  <div>
                    <div className="journal-stock">{entry.stock_name}</div>
                    <div className="journal-date">{entry.action} on {formatDate(entry.purchase_date)} · {entry.ticker}</div>
                  </div>
                  <div className="journal-price">
                    <div className="journal-price-val">₹{Number(entry.price).toLocaleString('en-IN')}</div>
                    <div className="journal-price-label">Entry Price</div>
                  </div>
                </div>
                <div className="journal-section">
                  <div className="journal-section-label">Why I bought this</div>
                  <div className="journal-section-text">{entry.reason}</div>
                </div>
                <div className="journal-section">
                  <div className="journal-section-label">Risks I identified</div>
                  <div className="journal-section-text">{entry.risks_identified}</div>
                </div>
                <div className="journal-footer">
                  <div className="confidence-badge">⬡ {entry.confidence}/10 confidence</div>
                  <div className="tag">{horizonLabels[entry.horizon] || entry.horizon} horizon</div>
                  {entry.quantity && <div className="tag">Qty: {entry.quantity}</div>}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="card" style={{height:'fit-content'}}>
          <div style={{fontSize:'14px',fontWeight:600,marginBottom:'16px'}}>Log a New Decision</div>
          
          <div className="form-group" style={{position:'relative'}}>
            <label className="form-label">Stock Name</label>
            <input className="form-input" type="text" placeholder="Search company..." value={companySearch} onChange={e => handleCompanySearch(e.target.value)} />
            {companyResults.length > 0 && (
              <div style={{position:'absolute',top:'100%',left:0,right:0,background:'var(--panel2)',border:'1px solid var(--border)',zIndex:10}}>
                {companyResults.map(c => (
                  <div key={c.id} style={{padding:'8px 12px',cursor:'pointer'}} onClick={() => selectCompany(c)}>
                    <span style={{color:'var(--accent)',marginRight:'8px'}}>{c.ticker}</span>{c.name}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
            <div className="form-group">
              <label className="form-label">Buy Price (₹)</label>
              <input className="form-input" type="number" value={form.price} onChange={e=>setForm(f=>({...f,price:e.target.value}))} />
            </div>
            <div className="form-group">
              <label className="form-label">Date</label>
              <input className="form-input" type="date" value={form.purchase_date} onChange={e=>setForm(f=>({...f,purchase_date:e.target.value}))} />
            </div>
          </div>
          
          <div className="form-group">
             <label className="form-label">Quantity</label>
             <input className="form-input" type="number" value={form.quantity} onChange={e=>setForm(f=>({...f,quantity:e.target.value}))} />
          </div>

          <div className="form-group">
            <label className="form-label">Why am I buying?</label>
            <textarea className="form-textarea" placeholder="What's the core thesis?" style={{minHeight:'70px'}} value={form.reason} onChange={e=>setForm(f=>({...f,reason:e.target.value}))} />
          </div>

          <div className="form-group">
            <label className="form-label">Risks I see</label>
            <textarea className="form-textarea" placeholder="What could go wrong?" style={{minHeight:'60px'}} value={form.risks_identified} onChange={e=>setForm(f=>({...f,risks_identified:e.target.value}))} />
          </div>

          <div className="form-group">
            <label className="form-label">Confidence: <span style={{color:'var(--accent)',fontFamily:'var(--mono)'}}>{form.confidence}</span>/10</label>
            <input type="range" className="confidence-slider" min="1" max="10" value={form.confidence} onChange={e=>setForm(f=>({...f,confidence:parseInt(e.target.value)}))} />
          </div>

          <div className="form-group">
             <label className="form-label">Horizon</label>
             <select className="form-select" value={form.horizon} onChange={e=>setForm(f=>({...f,horizon:e.target.value}))}>
               {HORIZONS.map(h=><option key={h.value} value={h.value}>{h.label}</option>)}
             </select>
          </div>

          <button className="save-btn" onClick={handleSubmit} disabled={saving}>{saving ? 'Saving...' : 'Save Decision →'}</button>
        </div>
      </div>
    </div>
  )
}
