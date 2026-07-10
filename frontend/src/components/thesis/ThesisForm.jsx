import { useState, useEffect } from 'react'
import { saveThesis, autoDraftThesis } from '../../lib/api'
import toast from 'react-hot-toast'
import { Sparkles } from 'lucide-react'

const HORIZONS = [
  { label: '6 Months', value: '6M' },
  { label: '1 Year', value: '1Y' },
  { label: '3 Years', value: '3Y' },
  { label: '5 Years', value: '5Y' }
]

export default function ThesisForm({ companyId, existingThesis, onSaved, documents = [] }) {
  const [form, setForm] = useState({
    why_interested: existingThesis?.why_interested || '',
    key_risks: existingThesis?.key_risks || '',
    expected_outcomes: existingThesis?.expected_outcomes || '',
    confidence: existingThesis?.confidence || 5,
    horizon: existingThesis?.horizon || '1Y',
  })
  const [saving, setSaving] = useState(false)
  const [selectedDocId, setSelectedDocId] = useState('')
  const [drafting, setDrafting] = useState(false)

  const readyDocs = (documents || []).filter(d => d.status === 'ready')

  useEffect(() => {
    if (readyDocs.length > 0 && !selectedDocId) {
      setSelectedDocId(readyDocs[0].id)
    }
  }, [documents])

  useEffect(() => {
    setForm({
      why_interested: existingThesis?.why_interested || '',
      key_risks: existingThesis?.key_risks || '',
      expected_outcomes: existingThesis?.expected_outcomes || '',
      confidence: existingThesis?.confidence || 5,
      horizon: existingThesis?.horizon || '1Y',
    })
  }, [existingThesis])

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    console.log('Submitting thesis with form state:', form)
    
    const why = String(form.why_interested || '')
    const risks = String(form.key_risks || '')
    const outcomes = String(form.expected_outcomes || '')

    if (!why.trim() || !risks.trim() || !outcomes.trim()) {
      toast.error('Please fill in all fields')
      return
    }

    setSaving(true)
    try {
      const payload = {
        company_id: companyId,
        why_interested: why,
        key_risks: risks,
        expected_outcomes: outcomes,
        confidence: form.confidence,
        horizon: form.horizon,
      }
      console.log('Sending saveThesis payload:', payload)
      const res = await saveThesis(payload)
      console.log('saveThesis response:', res.data)
      toast.success('Thesis saved!')
      onSaved?.()
    } catch (err) {
      console.error('Failed to save thesis:', err)
      toast.error(err.response?.data?.detail || 'Failed to save thesis')
    } finally {
      setSaving(false)
    }
  }

  const handleAutoFill = async () => {
    if (!selectedDocId) {
      toast.error('Please select a document first')
      return
    }
    setDrafting(true)
    try {
      const res = await autoDraftThesis(companyId, selectedDocId)
      
      const formatField = (val) => {
        if (!val) return ''
        if (Array.isArray(val)) {
          return val.map(item => typeof item === 'string' ? item : JSON.stringify(item)).join('\n')
        }
        if (typeof val === 'object') {
          return JSON.stringify(val, null, 2)
        }
        return String(val)
      }

      setForm(prev => ({
        ...prev,
        why_interested: formatField(res.data.why_interested),
        key_risks: formatField(res.data.key_risks),
        expected_outcomes: formatField(res.data.expected_outcomes),
      }))
      toast.success('Thesis auto-drafted! Review and click Save Thesis when ready.')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to generate auto-draft')
    } finally {
      setDrafting(false)
    }
  }

  return (
    <div className="thesis-layout">
      <div>
        <div className="card" style={{ marginBottom: '16px', display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
            <label className="form-label">Auto-draft from Report</label>
            <select 
              className="form-select" 
              value={selectedDocId} 
              onChange={e => setSelectedDocId(e.target.value)}
              disabled={readyDocs.length === 0 || drafting}
            >
              {readyDocs.length === 0 ? (
                <option value="">No processed reports available</option>
              ) : (
                readyDocs.map(d => (
                  <option key={d.id} value={d.id}>{d.filename}</option>
                ))
              )}
            </select>
          </div>
          <button 
            className="save-btn" 
            style={{ width: 'auto', padding: '10px 20px', height: '38px', whiteSpace: 'nowrap', display: 'inline-flex', alignItems: 'center', gap: '6px' }} 
            onClick={handleAutoFill}
            disabled={readyDocs.length === 0 || drafting}
          >
            {drafting ? 'Generating Draft...' : <><Sparkles size={14} /> Auto-fill</>}
          </button>
        </div>

        <div className="card" style={{ marginBottom: '16px' }}>
          <div className="form-group">
            <label className="form-label">Why am I interested?</label>
            <textarea
              className="form-textarea"
              placeholder="E.g. JLR turnaround, strong EV positioning..."
              value={form.why_interested}
              onChange={(e) => handleChange('why_interested', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Key risks I've identified</label>
            <textarea
              className="form-textarea"
              placeholder="E.g. China slowdown, commodity prices..."
              value={form.key_risks}
              onChange={(e) => handleChange('key_risks', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Expected outcomes — how will I know if thesis is working?</label>
            <textarea
              className="form-textarea"
              placeholder="Set measurable milestones..."
              value={form.expected_outcomes}
              onChange={(e) => handleChange('expected_outcomes', e.target.value)}
            />
          </div>
          <button className="save-btn" onClick={handleSubmit} disabled={saving}>
            {saving ? 'Saving...' : 'Save Thesis →'}
          </button>
        </div>
      </div>

      <div>
        <div className="confidence-panel">
          <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '16px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px' }}>Confidence Score</div>
          <div className="gauge-wrap">
            <svg className="gauge-svg" viewBox="0 0 100 100">
              <circle className="gauge-track" cx="50" cy="50" r="40" strokeDasharray="251" strokeDashoffset="0" />
              <circle 
                className="gauge-fill" 
                id="gaugeArc" 
                cx="50" cy="50" r="40" 
                style={{ strokeDashoffset: 251 - (251 * (form.confidence / 10) * 0.88), stroke: 'var(--accent)' }} 
              />
            </svg>
            <div className="gauge-center">
              <div className="gauge-number" id="gaugeNum">{form.confidence}</div>
              <div className="gauge-label">out of 10</div>
            </div>
          </div>
          <input 
            type="range" 
            className="confidence-slider" 
            min="1" max="10" 
            value={form.confidence} 
            onChange={(e) => handleChange('confidence', parseInt(e.target.value))} 
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--muted)' }}>
            <span>Low</span><span>High</span>
          </div>

          <div style={{ marginTop: '20px' }}>
            <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px' }}>Investment Horizon</div>
            <div className="horizon-pills">
              {HORIZONS.map((h) => (
                <div 
                  key={h.value} 
                  className={`horizon-pill ${form.horizon === h.value ? 'selected' : ''}`}
                  onClick={() => handleChange('horizon', h.value)}
                >
                  {h.label}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
