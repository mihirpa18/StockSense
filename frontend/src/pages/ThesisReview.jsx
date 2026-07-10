import { useEffect, useState } from 'react'
import { getWatchlist, getThesis, reviewThesis } from '../lib/api'
import { supabase } from '../lib/supabase'
import { useAuth } from '../hooks/useAuth'
import toast from 'react-hot-toast'
import { Check, AlertTriangle, X } from 'lucide-react'

export default function ThesisReview() {
  const { user } = useAuth()
  const [watchlist, setWatchlist] = useState([])
  const [selectedCompany, setSelectedCompany] = useState('')
  const [thesis, setThesis] = useState(null)
  const [documents, setDocuments] = useState([])
  const [selectedDoc, setSelectedDoc] = useState('')
  const [reviewMode, setReviewMode] = useState('document') // 'document' | 'hybrid' | 'web'
  const [searchQuery, setSearchQuery] = useState('')
  const [reviewing, setReviewing] = useState(false)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadWatchlist() }, [])

  const loadWatchlist = async () => {
    try {
      const res = await getWatchlist()
      setWatchlist(res.data || [])
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const handleCompanySelect = async (companyId) => {
    setSelectedCompany(companyId)
    setResult(null)
    setSelectedDoc('')
    setReviewMode('document')
    try {
      const thesisRes = await getThesis(companyId)
      const currentThesis = thesisRes.data
      setThesis(currentThesis)

      if (currentThesis) {
        const watchItem = watchlist.find(w => w.company_id === companyId)
        const companyTicker = watchItem ? watchItem.companies.ticker : ''
        
        const cleanText = (text) => text ? text.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 50) : ''
        const interest = cleanText(currentThesis.why_interested)
        const risks = cleanText(currentThesis.key_risks)
        
        setSearchQuery(`${companyTicker} ${interest} ${risks}`.trim())
      } else {
        setSearchQuery('')
      }

      const { data: docs } = await supabase.from('documents').select('*').eq('company_id', companyId).eq('user_id', user?.id).eq('status', 'ready').order('uploaded_at', { ascending: false })
      setDocuments(docs || [])
    } catch {
      setThesis(null)
      setDocuments([])
      setSearchQuery('')
    }
  }

  const handleReview = async () => {
    if (!thesis?.id) { toast.error('No active thesis saved'); return }
    if (reviewMode !== 'web' && !selectedDoc) { toast.error('Select a document'); return }
    if (reviewMode !== 'document' && !searchQuery.trim()) { toast.error('Enter a search query'); return }

    setReviewing(true)
    try {
      const res = await reviewThesis(thesis.id, selectedDoc, reviewMode, searchQuery)
      setResult(res.data)
      toast.success('Review complete!')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Review failed')
    } finally { setReviewing(false) }
  }

  if (loading) return <div style={{padding:'24px'}}>Loading...</div>

  return (
    <div className="view active">
      <div className="page-title">Thesis Review Engine</div>
      <div className="page-sub">AI compares your original assumptions against the latest uploaded reports.</div>

      <div className="card" style={{marginBottom:'20px'}}>
        <div style={{fontSize:'13px',fontWeight:600,marginBottom:'14px'}}>Setup Review</div>

        <div className="form-group">
          <label className="form-label">Company</label>
          <select value={selectedCompany} onChange={e => handleCompanySelect(e.target.value)} className="form-select">
            <option value="">Select a company...</option>
            {watchlist.map(w => <option key={w.company_id} value={w.company_id}>{w.companies.name} ({w.companies.ticker})</option>)}
          </select>
        </div>

        {thesis && (
          <div style={{background:'var(--panel2)',padding:'14px',borderRadius:'8px',marginBottom:'14px'}}>
            <div style={{fontSize:'12px',color:'var(--muted)',marginBottom:'8px'}}>Active Thesis</div>
            <div style={{fontSize:'13px',color:'var(--sub)'}}>{thesis.why_interested?.slice(0, 150)}...</div>
          </div>
        )}

        {selectedCompany && !thesis && <p style={{color:'var(--amber)',fontSize:'13px',marginBottom:'14px'}}>No thesis saved for this company. Create one first.</p>}

        {thesis && (
          <div className="form-group">
            <label className="form-label">Review Mode</label>
            <select value={reviewMode} onChange={e => { setReviewMode(e.target.value); setSelectedDoc(''); }} className="form-select">
              <option value="document">Document Only</option>
              <option value="hybrid">Document + Web Search</option>
              <option value="web">Web Search Only</option>
            </select>
          </div>
        )}

        {thesis && reviewMode !== 'web' && (
          <div className="form-group">
            <label className="form-label">Review Against Document</label>
            {documents.length > 0 ? (
              <select value={selectedDoc} onChange={e => setSelectedDoc(e.target.value)} className="form-select">
                <option value="">Select a document...</option>
                {documents.map(d => <option key={d.id} value={d.id}>{d.filename} ({d.fiscal_year})</option>)}
              </select>
            ) : (
              <p style={{color:'var(--amber)',fontSize:'13px'}}>No documents uploaded. Choose 'Web Search Only' or upload a document first.</p>
            )}
          </div>
        )}

        {thesis && reviewMode !== 'document' && (
          <div className="form-group">
            <label className="form-label">Web Search Query (Editable)</label>
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="form-select"
              style={{width: '100%', padding: '10px', background: 'var(--panel2)', border: '1px solid var(--border)', borderRadius: '6px', color: 'var(--text)'}}
              placeholder="Enter web search query..."
            />
          </div>
        )}

        {thesis && (
          (reviewMode === 'web' && searchQuery.trim()) ||
          (reviewMode === 'document' && selectedDoc) ||
          (reviewMode === 'hybrid' && selectedDoc && searchQuery.trim())
        ) && (
          <button onClick={handleReview} disabled={reviewing} className="save-btn">
            {reviewing ? 'Reviewing...' : 'Run Review →'}
          </button>
        )}
      </div>

      {result && (
        <div>
          <div className="card" style={{marginBottom:'20px'}}>
            <div style={{fontSize:'13px',fontWeight:600,marginBottom:'10px'}}>Review Results</div>
            <div style={{fontSize:'13px',color:'var(--sub)',lineHeight:1.6}}>{result.summary}</div>
          </div>

          <div>
             {result.assumptions?.map((a, i) => (
                <div key={i} className="review-card">
                   <div className="review-header">
                     <div className={`review-status ${a.status === 'supported' ? 'status-ok' : a.status === 'weakening' ? 'status-warn' : 'status-bad'}`}>
                       {a.status === 'supported' ? <Check size={14} /> : a.status === 'weakening' ? <AlertTriangle size={13} /> : <X size={14} />}
                     </div>
                     <div className="review-assumption">{a.assumption}</div>
                   </div>
                   <div className="review-evidence">{a.evidence}</div>
                   {a.source_page && <div className="review-source">Page {a.source_page}</div>}
                </div>
             ))}
          </div>
        </div>
      )}
    </div>
  )
}
