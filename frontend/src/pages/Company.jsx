import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getCompany,
  getCompanyFundamentals,
  uploadDocument,
  addToWatchlist,
  removeFromWatchlist,
  getWatchlist,
  getThesis,
  triggerAutoResearch,
  refreshPrice,
  refreshFundamentals,
  getNotes,
  saveNote
} from '../lib/api'
import { supabase } from '../lib/supabase'
import { useAuth } from '../hooks/useAuth'
import ChatPanel from '../components/chat/ChatPanel'
import ThesisForm from '../components/thesis/ThesisForm'
import TradingViewWidget from '../components/TradingViewWidget'
import Markdown from '../components/ui/Markdown'
import toast from 'react-hot-toast'
import {
  FlaskConical, BarChart3, ClipboardList, FileEdit,
  Star, IndianRupee, RefreshCw, Sparkles, Building2, Newspaper,
  FileText, CheckCircle2, UploadCloud, Plus, Clock
} from 'lucide-react'

const TABS = [
  { id: 'research',    label: 'AI Research',    icon: FlaskConical },
  { id: 'financials',  label: 'Financials',      icon: BarChart3 },
  { id: 'thesis',      label: 'Thesis Builder',  icon: ClipboardList },
  { id: 'notes',       label: 'Notes',           icon: FileEdit },
]

export default function Company() {
  const { id: companyId } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [company, setCompany] = useState(null)
  const [fundamentals, setFundamentals] = useState(null)
  const [documents, setDocuments] = useState([])
  const [selectedDocId, setSelectedDocId] = useState(null)
  const [thesis, setThesis] = useState(null)
  const [notes, setNotes] = useState('')
  const [notesList, setNotesList] = useState([])
  const [selectedNoteId, setSelectedNoteId] = useState(null)
  const [isWatched, setIsWatched] = useState(false)
  const [activeTab, setActiveTab] = useState('research')
  const [uploading, setUploading] = useState(false)
  const [autoResearching, setAutoResearching] = useState(false)
  const [agentResult, setAgentResult] = useState(null)
  const [candidateUrls, setCandidateUrls] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshingPrice, setRefreshingPrice] = useState(false)
  const [refreshingFundamentals, setRefreshingFundamentals] = useState(false)
  const [financialsPeriod, setFinancialsPeriod] = useState('annual')

  useEffect(() => {
    if (companyId && user?.id) {
      setSelectedDocId(null)
      setNotes('')
      setNotesList([])
      setSelectedNoteId(null)
      setThesis(null)
      setActiveTab('research')
      setAgentResult(null)
      setCandidateUrls([])
      loadCompanyData()
    }
  }, [companyId, user?.id])

  const loadCompanyData = async () => {
    setLoading(true)
    try {
      const [compRes, fundRes] = await Promise.all([
        getCompany(companyId),
        getCompanyFundamentals(companyId).catch(() => ({ data: null }))
      ])
      setCompany(compRes.data)
      setFundamentals(fundRes.data)

      // Auto-refresh price on every visit (lightweight, NSE node only)
      try {
        const priceRes = await refreshPrice(companyId)
        setFundamentals(prev => ({ ...prev, ...priceRes.data }))
      } catch (e) {
        console.warn('Price auto-refresh failed, using cached:', e)
      }

      await fetchDocuments()

      try {
        const thesisRes = await getThesis(companyId)
        setThesis(thesisRes.data)
      } catch { setThesis(null) }

      try {
        const notesRes = await getNotes(companyId)
        setNotesList(notesRes.data || [])
        setNotes('')
        setSelectedNoteId(null)
      } catch {
        setNotesList([])
      }

      const watchRes = await getWatchlist()
      const watched = (watchRes.data || []).some(w => w.company_id === companyId)
      setIsWatched(watched)
    } catch (err) {
      console.error('Load error:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchDocuments = async () => {
    const { data } = await supabase
      .from('documents')
      .select('*')
      .eq('company_id', companyId)
      .eq('user_id', user?.id)
      .neq('status', 'failed')
      .order('uploaded_at', { ascending: false })
    setDocuments(data || [])
    if (data?.length > 0 && !selectedDocId) {
      const readyDoc = data.find(d => d.status === 'ready') || data[0]
      setSelectedDocId(readyDoc?.id || null)
    }
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('company_id', companyId)
      formData.append('doc_type', 'annual_report')
      formData.append('fiscal_year', 'FY24')

      const res = await uploadDocument(formData)
      toast.success(`Processed ${res.data.page_count} pages, ${res.data.chunk_count} chunks`)
      await fetchDocuments()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleAutoResearch = async () => {
    setAutoResearching(true)
    setCandidateUrls([])
    try {
      const res = await triggerAutoResearch(companyId)
      
      if (res.data.status === 'pending_confirmation') {
         // Save news summary/items immediately
         setAgentResult({
           news_summary: res.data.news_summary,
           news_items: res.data.news_items || [],
           pdf_processed: false
         })
         // Save candidate URLs for UI selection list
         setCandidateUrls(res.data.candidate_urls || [])
         toast('Discovered candidate reports! Select one to ingest.', { icon: '🔍' })
      } else {
        setAgentResult(res.data)
        if (res.data.pdf_processed) {
          toast.success('Report processed! You can now ask questions.')
          await fetchDocuments()
        } else {
          toast('News summary ready. Upload PDF for full research.', { icon: '⚠️' })
        }
      }
    } catch (err) {
      toast.error('Auto research failed.')
    } finally {
      setAutoResearching(false)
    }
  }

  const handleIngestCandidate = async (url) => {
    setAutoResearching(true)
    toast('Processing PDF report...', { icon: '⏳' })
    try {
      const newsFromFirstCall = {
        news_summary: agentResult?.news_summary,
        news_items: agentResult?.news_items || []
      }
      const processRes = await triggerAutoResearch(companyId, { target_url: url })
      setAgentResult({ ...processRes.data, ...newsFromFirstCall })
      if (processRes.data.pdf_processed) {
        toast.success('Report processed successfully!')
        setCandidateUrls([]) // Clear list on success
        await fetchDocuments()
      } else {
        toast.error('Failed to process the selected PDF.')
      }
    } catch {
      toast.error('PDF ingestion failed.')
    } finally {
      setAutoResearching(false)
    }
  }

  const handleWatchlistToggle = async () => {
    try {
      if (isWatched) {
        await removeFromWatchlist(companyId)
        setIsWatched(false)
        toast.success('Removed from watchlist')
      } else {
        await addToWatchlist(companyId)
        setIsWatched(true)
        toast.success('Added to watchlist')
      }
    } catch {
      toast.error('Failed to update watchlist')
    }
  }

  const formatDateTime = (dateStr) => {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return dateStr
    const day = String(d.getDate()).padStart(2, '0')
    const month = String(d.getMonth() + 1).padStart(2, '0')
    const year = d.getFullYear()
    const hours = String(d.getHours()).padStart(2, '0')
    const minutes = String(d.getMinutes()).padStart(2, '0')
    return `${day}-${month}-${year} ${hours}:${minutes}`
  }

  const handleNoteSave = async () => {
    if (!notes.trim()) {
      toast.error('Note content cannot be empty')
      return
    }
    try {
      const payload = {
        company_id: companyId,
        content: notes
      }
      if (selectedNoteId) {
        payload.id = selectedNoteId
      }
      const res = await saveNote(payload)
      toast.success(selectedNoteId ? 'Note updated' : 'Note saved')
      
      const notesRes = await getNotes(companyId)
      setNotesList(notesRes.data || [])
      
      if (!selectedNoteId) {
        setNotes('')
      }
    } catch {
      toast.error('Failed to save notes')
    }
  }

  const handleRefreshPrice = async () => {
    setRefreshingPrice(true)
    try {
      const res = await refreshPrice(companyId)
      setFundamentals(prev => ({ ...prev, ...res.data }))
      toast.success('Price updated')
    } catch {
      toast.error('Price refresh failed')
    } finally {
      setRefreshingPrice(false)
    }
  }

  const handleRefreshFundamentals = async () => {
    setRefreshingFundamentals(true)
    try {
      const res = await refreshFundamentals(companyId)
      setFundamentals(res.data)
      toast.success('Fundamentals updated')
    } catch {
      toast.error('Fundamentals refresh failed')
    } finally {
      setRefreshingFundamentals(false)
    }
  }

  const formatPercent = (val) => val != null ? `${(val * 100).toFixed(1)}%` : 'N/A'
  const formatRatio = (val) => val != null ? val.toFixed(1) + 'x' : 'N/A'
  const formatPrice = (val) => val != null ? `₹${val.toLocaleString('en-IN')}` : 'N/A'
  const formatCap = (val) => {
    if (!val) return 'N/A'
    if (val >= 1e12) return `₹${(val / 1e12).toFixed(1)}T`
    if (val >= 1e9) return `₹${(val / 1e9).toFixed(0)}B`
    return `₹${(val / 1e7).toFixed(0)}Cr`
  }

  if (loading) {
    return <div style={{padding: '20px'}}>Loading...</div>
  }

  if (!company) {
    return <div style={{padding: '20px'}}>Company not found</div>
  }

  return (
    <div className="view active">
      <div className="company-header">
        <div className="company-logo">{company.ticker.slice(0, 2)}</div>
        <div className="company-info">
          <div className="company-name">{company.name}</div>
          <div className="company-meta">{company.exchange}: {company.ticker} · {company.sector}</div>
          <div className="company-desc">{company.description || 'No description available.'}</div>
          <div className="company-stats">
            <div className="stat-item"><div className="stat-label">Market Cap</div><div className="stat-value">{formatCap(fundamentals?.market_cap)}</div></div>
            <div className="stat-item"><div className="stat-label">CMP</div><div className="stat-value">{formatPrice(fundamentals?.current_price)}</div></div>
            {fundamentals?.pChange != null && (
              <div className="stat-item">
                <div className="stat-label">Change</div>
                <div className="stat-value" style={{ color: fundamentals.pChange > 0 ? 'var(--green)' : fundamentals.pChange < 0 ? 'var(--red)' : 'var(--muted)' }}>
                  {fundamentals.pChange > 0 ? '+' : ''}{fundamentals.pChange}%
                </div>
              </div>
            )}
          </div>
          <div style={{ marginTop: '16px', height: '350px', width: '100%', borderRadius: '8px', overflow: 'hidden' }}>
            <TradingViewWidget ticker={company.ticker} exchange="BSE" />
          </div>
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:'8px'}}>
          <button
            className="btn-outline"
            style={{width:'170px', padding:'8px', display:'flex', alignItems:'center', justifyContent:'center', gap:'6px'}}
            onClick={handleRefreshPrice}
            disabled={refreshingPrice}
          >
            {refreshingPrice ? <><RefreshCw size={13} className="spin" /> Updating...</> : <><IndianRupee size={13} /> Refresh Price</>}
          </button>
          <button
            className="btn-outline"
            style={{width:'170px', padding:'8px', display:'flex', alignItems:'center', justifyContent:'center', gap:'6px'}}
            onClick={handleRefreshFundamentals}
            disabled={refreshingFundamentals}
          >
            {refreshingFundamentals ? <><RefreshCw size={13} className="spin" /> Updating...</> : <><BarChart3 size={13} /> Refresh Fundamentals</>}
          </button>
          <button className={isWatched ? 'save-btn' : 'btn-outline'} style={{width:'170px',padding:'8px', display:'flex', alignItems:'center', justifyContent:'center', gap:'6px'}} onClick={handleWatchlistToggle}>
            <Star size={13} fill={isWatched ? 'currentColor' : 'none'} /> {isWatched ? 'Watchlisted' : 'Watch'}
          </button>
        </div>
      </div>

      {fundamentals?.fifty_two_week_low != null && fundamentals?.fifty_two_week_high != null && (() => {
        const lo = fundamentals.fifty_two_week_low
        const hi = fundamentals.fifty_two_week_high
        const cur = fundamentals.current_price
        const pct = cur != null && hi > lo
          ? Math.min(100, Math.max(0, ((cur - lo) / (hi - lo)) * 100))
          : null
        return (
          <div className="card range-card">
            <div className="range-card-header">
              <span className="card-label" style={{ marginBottom: 0 }}>52-Week Range</span>
              {cur != null && <span className="range-current">{formatPrice(cur)}</span>}
            </div>
            <div className="range-track">
              <div className="range-fill" style={{ width: pct != null ? `${pct}%` : '0%' }} />
              {pct != null && (
                <div className="range-marker" style={{ left: `${pct}%` }} title={`Current: ${formatPrice(cur)}`} />
              )}
            </div>
            <div className="range-labels">
              <span>{formatPrice(lo)} <span className="range-labels-tag">52W Low</span></span>
              <span>{formatPrice(hi)} <span className="range-labels-tag">52W High</span></span>
            </div>
          </div>
        )
      })()}

      {fundamentals && (
        <div className="fundamentals">
          <div className="fund-card" title="Price-to-Earnings Ratio: Measures the share price relative to per-share earnings. Indicates how much the market is willing to pay.">
            <div className="fund-label">
              P/E Ratio 
              <span 
                className="fund-tooltip" 
                data-tooltip="Price-to-Earnings Ratio: Measures the share price relative to per-share earnings. Indicates how much the market is willing to pay."
              >?</span>
            </div>
            <div className="fund-value">{formatRatio(fundamentals.pe_ratio)}</div>
          </div>
          <div className="fund-card" title="Return on Equity: Profitability generated relative to shareholder equity. Shows efficiency at turning capital into profit.">
            <div className="fund-label">
              ROE 
              <span 
                className="fund-tooltip" 
                data-tooltip="Return on Equity: Profitability generated relative to shareholder equity. Shows efficiency at turning capital into profit."
              >?</span>
            </div>
            <div className="fund-value">{formatPercent(fundamentals.roe)}</div>
          </div>
          <div className="fund-card" title="Revenue Growth: Year-over-year growth in sales. Indicates business expansion and market demand.">
            <div className="fund-label">
              Revenue Growth 
              <span 
                className="fund-tooltip" 
                data-tooltip="Revenue Growth: Year-over-year growth in sales. Indicates business expansion and market demand."
              >?</span>
            </div>
            <div className="fund-value">{formatPercent(fundamentals.revenue_growth)}</div>
          </div>
          <div className="fund-card" title="Debt/Equity Ratio: Proportion of debt relative to equity capital. High leverage increases financial risk.">
            <div className="fund-label">
              Debt/Equity 
              <span 
                className="fund-tooltip" 
                data-tooltip="Debt/Equity Ratio: Proportion of debt relative to equity capital. High leverage increases financial risk."
              >?</span>
            </div>
            <div className="fund-value">{formatRatio(fundamentals.debt_to_equity)}</div>
          </div>
          <div className="fund-card" title="Net Profit Margin: Percentage of revenue left as profit after all expenses. Shows pricing power and efficiency.">
            <div className="fund-label">
              Net Margin 
              <span 
                className="fund-tooltip" 
                data-tooltip="Net Profit Margin: Percentage of revenue left as profit after all expenses. Shows pricing power and efficiency."
              >?</span>
            </div>
            <div className="fund-value">{formatPercent(fundamentals.profit_margin)}</div>
          </div>
        </div>
      )}

      {(fundamentals?.about || fundamentals?.news?.length > 0) && (
        <div className="about-news-row">
          {fundamentals?.about && (
            <div className="card">
              <div className="section-title"><Building2 size={15} /> About</div>
              <div className="about-grid">
                <div>
                  <div className="about-label">CEO</div>
                  <div className="about-value">{fundamentals.about.ceo || 'N/A'}</div>
                </div>
                <div>
                  <div className="about-label">Founded</div>
                  <div className="about-value">{fundamentals.about.founded || 'N/A'}</div>
                </div>
                <div>
                  <div className="about-label">Employees</div>
                  <div className="about-value">{fundamentals.about.employees || 'N/A'}</div>
                </div>
                <div>
                  <div className="about-label">Headquarters</div>
                  <div className="about-value">{fundamentals.about.headquarters || 'N/A'}</div>
                </div>
              </div>
            </div>
          )}

          {fundamentals?.news?.length > 0 && (
            <div className="card">
              <div className="section-title"><Newspaper size={15} /> Recent News</div>
              {fundamentals.news.map((item, i) => (
                <a
                  key={i}
                  href={item.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="news-item"
                >
                  <div className="news-headline">{item.headline}</div>
                  <div className="news-meta">
                    {item.source}{item.source && item.date ? ' · ' : ''}{item.date}
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="tabs">
        {TABS.map(({ id, label, icon: Icon }) => (
          <div
            key={id}
            onClick={() => setActiveTab(id)}
            className={`tab ${activeTab === id ? 'active' : ''}`}
          >
            <Icon size={14} /> {label}
          </div>
        ))}
      </div>

      {activeTab === 'research' && (
        <div className="tab-content active" id="tab-research">
          <div className="research-layout">
            <div className="chat-panel" style={{height: '600px'}}>
              <ChatPanel 
                companyId={companyId} 
                documentId={selectedDocId} 
                companyName={company?.name}
                companySector={company?.sector}
              />
            </div>

            <div style={{display:'flex',flexDirection:'column',gap:'14px'}}>
              <div className="upload-panel">
                <div style={{fontSize:'13px',fontWeight:600,marginBottom:'2px'}}>Documents</div>
                
                {documents.filter(doc => doc.status !== 'failed').map((doc) => (
                  <div 
                    key={doc.id} 
                    className="uploaded-doc" 
                    style={selectedDocId === doc.id ? { borderColor: 'var(--accent)' } : { cursor: 'pointer' }}
                    onClick={() => setSelectedDocId(doc.id)}
                  >
                    <div className="doc-icon"><FileText size={16} /></div>
                    <div>
                      <div className="doc-name">{doc.filename}</div>
                      <div className="doc-size">{doc.page_count} pages</div>
                    </div>
                    <div className="doc-status"><CheckCircle2 size={11} /> {doc.status}</div>
                  </div>
                ))}
                
                {selectedDocId && (
                  <div style={{ fontSize: '12px', color: 'var(--accent)', marginTop: '4px' }}>
                    Document selected for chat. The AI assistant will use this document to answer your questions.
                  </div>
                )}

                <label className="upload-zone">
                  <div className="upload-icon"><UploadCloud size={22} /></div>
                  <div className="upload-text">{uploading ? 'Uploading...' : 'Drop report here or browse'}</div>
                  <input type="file" accept=".pdf" className="hidden" style={{display:'none'}} onChange={handleUpload} disabled={uploading} />
                </label>
                
                <button
                  onClick={handleAutoResearch}
                  disabled={autoResearching}
                  className="btn-outline"
                  style={{width: '100%', marginTop: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px'}}
                >
                  {autoResearching ? 'Researching...' : <><Sparkles size={13} /> Auto Research</>}
                </button>
              </div>

              {candidateUrls.length > 0 && (
                <div className="upload-panel" style={{ borderColor: 'var(--amber)', background: 'rgba(245,158,11,0.03)' }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--amber)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>🔍 Discovered Reports ({candidateUrls.length})</span>
                    <button 
                      onClick={() => setCandidateUrls([])} 
                      style={{ background: 'transparent', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: '11px' }}
                    >
                      Dismiss
                    </button>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px', maxHeight: '180px', overflowY: 'auto' }}>
                    {candidateUrls.map((url, i) => {
                      let domain = 'Report Link'
                      try { domain = new URL(url).hostname.replace('www.', '') } catch {}
                      return (
                        <div key={i} className="uploaded-doc" style={{ justifyContent: 'space-between', padding: '8px 10px', cursor: 'default' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                            <div className="doc-icon" style={{ color: 'var(--amber)' }}><FileText size={14} /></div>
                            <a 
                              href={url} 
                              target="_blank" 
                              rel="noopener noreferrer" 
                              className="doc-name" 
                              style={{ fontSize: '12px', color: 'inherit', textDecoration: 'underline', textUnderlineOffset: '3px' }}
                              title={`Click to open PDF: ${url}`}
                            >
                              {domain} ↗
                            </a>
                          </div>
                          <button
                            onClick={() => handleIngestCandidate(url)}
                            disabled={autoResearching}
                            className="save-btn"
                            style={{ width: 'auto', padding: '3px 8px', fontSize: '11px', marginTop: 0 }}
                          >
                            Ingest
                          </button>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {agentResult?.news_summary && (
                <div className="upload-panel">
                   <div className="sq-title">AI News Summary</div>
                   <div style={{fontSize: '12.5px', color: 'var(--sub)', lineHeight: '1.5'}}>
                     <Markdown content={agentResult.news_summary} />
                   </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'financials' && (
        <div className="tab-content active" id="tab-financials">
          <div className="card">
            {(() => {
              const periods = fundamentals?.financials?.[financialsPeriod] || []
              // SerpApi returns most-recent-first; chart reads left-to-right chronologically.
              const chronological = [...periods].reverse()
              const maxVal = Math.max(
                1,
                ...chronological.map((p) => Math.max(Math.abs(p.revenue || 0), Math.abs(p.net_income || 0)))
              )

              if (periods.length === 0) {
                return (
                  <div style={{ textAlign: 'center', padding: '50px 20px', color: 'var(--muted)' }}>
                    <div style={{ fontSize: '13px', marginBottom: '12px' }}>
                      No financial statement data cached for this company yet.
                    </div>
                    <button
                      className="btn-outline"
                      style={{ width: 'auto', padding: '8px 20px', margin: '0 auto', display: 'flex', alignItems: 'center', gap: '6px' }}
                      onClick={handleRefreshFundamentals}
                      disabled={refreshingFundamentals}
                    >
                      {refreshingFundamentals ? <><RefreshCw size={13} className="spin" /> Fetching...</> : <><BarChart3 size={13} /> Fetch Financials</>}
                    </button>
                  </div>
                )
              }

              return (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <div className="section-title" style={{ marginBottom: 0 }}>Revenue &amp; Net Income</div>
                    <div className="period-toggle">
                      <div
                        className={`period-btn ${financialsPeriod === 'annual' ? 'active' : ''}`}
                        onClick={() => setFinancialsPeriod('annual')}
                      >
                        Annual
                      </div>
                      <div
                        className={`period-btn ${financialsPeriod === 'quarterly' ? 'active' : ''}`}
                        onClick={() => setFinancialsPeriod('quarterly')}
                      >
                        Quarterly
                      </div>
                    </div>
                  </div>

                  <div className="fin-legend">
                    <div className="fin-legend-item">
                      <div className="fin-legend-dot" style={{ background: 'var(--accent)' }} />
                      Revenue
                    </div>
                    <div className="fin-legend-item">
                      <div className="fin-legend-dot" style={{ background: 'var(--green)' }} />
                      Net Income
                    </div>
                  </div>

                  <div className="fin-chart">
                    {chronological.map((p, i) => (
                      <div key={i} className="fin-bar-group">
                        <div className="fin-bars">
                          <div
                            className="fin-bar revenue"
                            style={{ height: `${Math.max(4, (Math.abs(p.revenue || 0) / maxVal) * 170)}px` }}
                            title={`Revenue: ${formatCap(p.revenue)}`}
                          />
                          <div
                            className={`fin-bar net-income ${(p.net_income || 0) < 0 ? 'negative' : ''}`}
                            style={{ height: `${Math.max(4, (Math.abs(p.net_income || 0) / maxVal) * 170)}px` }}
                            title={`Net Income: ${formatCap(p.net_income)}`}
                          />
                        </div>
                        <div className="fin-bar-label">{p.date || '—'}</div>
                      </div>
                    ))}
                  </div>

                  <div className="fin-table-scroll">
                  <table className="fin-table">
                    <thead>
                      <tr>
                        <th>Period</th>
                        <th>Revenue</th>
                        <th>Net Income</th>
                        <th>Net Margin</th>
                      </tr>
                    </thead>
                    <tbody>
                      {periods.map((p, i) => (
                        <tr key={i}>
                          <td>{p.date || '—'}</td>
                          <td>{formatCap(p.revenue)}</td>
                          <td style={{ color: (p.net_income || 0) < 0 ? 'var(--red)' : 'inherit' }}>
                            {formatCap(p.net_income)}
                          </td>
                          <td>{p.revenue ? formatPercent(p.net_income / p.revenue) : 'N/A'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>
                </>
              )
            })()}
          </div>
        </div>
      )}

      {activeTab === 'thesis' && (
        <div className="tab-content active" id="tab-thesis">
          {thesis?.updated_at && (
            <div style={{
              fontSize: '12px',
              color: 'var(--muted)',
              marginBottom: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <Clock size={12} /> Last saved: {formatDateTime(thesis.updated_at)}
            </div>
          )}
          <ThesisForm
            companyId={companyId}
            existingThesis={thesis}
            onSaved={() => loadCompanyData()}
            documents={documents}
          />
        </div>
      )}

      {activeTab === 'notes' && (
        <div className="tab-content active" id="tab-notes">
          <div className="notes-layout">
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <div style={{ fontSize: '13px', fontWeight: 600 }}>
                  {selectedNoteId ? 'Edit Note' : 'New Research Note'} — {company.name}
                </div>
                {selectedNoteId && (
                  <button
                    className="btn-outline"
                    style={{ padding: '4px 10px', fontSize: '12px', width: 'auto', display: 'flex', alignItems: 'center', gap: '5px' }}
                    onClick={() => {
                      setSelectedNoteId(null)
                      setNotes('')
                    }}
                  >
                    <Plus size={12} /> Write New Note
                  </button>
                )}
              </div>
              <textarea
                className="form-textarea"
                style={{ minHeight: '240px', marginBottom: '14px' }}
                placeholder="Add your personal notes here..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
              <button 
                className="save-btn" 
                style={{ width: 'auto', padding: '8px 20px' }} 
                onClick={handleNoteSave}
              >
                {selectedNoteId ? 'Update Note →' : 'Save Note →'}
              </button>
            </div>

            <div className="card" style={{ height: 'fit-content', maxHeight: '400px', overflowY: 'auto' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '14px' }}>Notes History</div>
              {notesList.length === 0 ? (
                <div style={{ color: 'var(--muted)', fontSize: '12.5px', textAlign: 'center', padding: '20px 0' }}>
                  No saved notes.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {notesList.map((note) => {
                    const words = note.content.trim().split(/\s+/)
                    const firstFewWords = words.slice(0, 5).join(' ') + (words.length > 5 ? '...' : '')
                    const displayTitle = firstFewWords || 'Empty note'
                    const isEditingThis = selectedNoteId === note.id
                    
                    return (
                      <div
                        key={note.id}
                        onClick={() => {
                          setSelectedNoteId(note.id)
                          setNotes(note.content)
                        }}
                        style={{
                          padding: '10px',
                          border: '1px solid var(--border)',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          background: isEditingThis ? 'rgba(var(--accent-rgb),0.1)' : 'var(--panel2)',
                          borderColor: isEditingThis ? 'var(--accent)' : 'var(--border)',
                          transition: 'all 0.15s'
                        }}
                        className="note-history-item"
                      >
                        <div style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--text)', marginBottom: '4px' }}>
                          {displayTitle}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--muted)' }}>
                          {formatDateTime(note.updated_at)}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
