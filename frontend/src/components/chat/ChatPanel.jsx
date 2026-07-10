import { useState, useRef, useEffect } from 'react'
import { sendChat, getChatSessions, getChatHistory } from '../../lib/api'
import Markdown from '../ui/Markdown'
import { Plus, History, Send } from 'lucide-react'

export default function ChatPanel({ companyId, documentId }) {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [input, setInput] = useState('')
  const [sessions, setSessions] = useState([])
  const [showSessions, setShowSessions] = useState(false)
  const [loadingSessions, setLoadingSessions] = useState(false)
  const messagesEndRef = useRef(null)
  const sessionsPanelRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Reset chat state and fetch sessions when company changes
  useEffect(() => {
    setMessages([])
    setSessionId(null)
    setShowSessions(false)
    if (companyId) {
      fetchSessions()
    }
  }, [companyId])

  // When document changes within the same company, only reset messages (keep sessions list)
  useEffect(() => {
    setMessages([])
    setSessionId(null)
  }, [documentId])

  // Close sessions panel on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (sessionsPanelRef.current && !sessionsPanelRef.current.contains(e.target)) {
        setShowSessions(false)
      }
    }
    if (showSessions) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showSessions])

  const fetchSessions = async () => {
    try {
      setLoadingSessions(true)
      const res = await getChatSessions(companyId)
      setSessions(res.data || [])
    } catch {
      setSessions([])
    } finally {
      setLoadingSessions(false)
    }
  }

  const loadSession = async (sid) => {
    try {
      setLoading(true)
      const res = await getChatHistory(sid)
      const history = res.data || []
      setMessages(history.map(msg => ({
        role: msg.role,
        content: msg.content,
        citations: msg.citations || []
      })))
      setSessionId(sid)
      setShowSessions(false)
    } catch {
      // Session might have been deleted
    } finally {
      setLoading(false)
    }
  }

  const startNewChat = () => {
    setMessages([])
    setSessionId(null)
    setShowSessions(false)
  }

  const handleSend = async (question) => {
    const q = question || input
    if (!q.trim() || loading) return

    const userMsg = { role: 'user', content: q }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await sendChat({
        company_id: companyId,
        question: q,
        session_id: sessionId,
        document_id: documentId || null,
        conversation_history: messages.slice(-4)
      })

      const data = res.data
      setSessionId(data.session_id)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          citations: data.citations
        }
      ])

      // Refresh sessions list after a new message (adds new session or updates existing)
      fetchSessions()
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, something went wrong. Please try again.',
          error: true
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  const formatTimeAgo = (dateStr) => {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    const now = new Date()
    const diffMs = now - d
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1) return 'just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    const diffDays = Math.floor(diffHours / 24)
    if (diffDays < 7) return `${diffDays}d ago`
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
  }

  return (
    <div style={{display:'flex',flexDirection:'column',height:'100%'}}>
      <div className="chat-header" style={{position:'relative'}}>
        <div className="ai-dot"></div>
        <span style={{flex:1}}>AI Research Assistant</span>
        <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
          <button
            className="chat-session-btn"
            onClick={startNewChat}
            title="New chat"
          >
            <Plus size={13} />
          </button>
          <button
            className={`chat-session-btn ${showSessions ? 'active' : ''}`}
            onClick={() => {
              setShowSessions(!showSessions)
              if (!showSessions) fetchSessions()
            }}
            title="Chat history"
          >
            <History size={13} />
          </button>
        </div>

        {showSessions && (
          <div className="chat-sessions-panel" ref={sessionsPanelRef}>
            <div className="chat-sessions-header">
              <span>Chat History</span>
              <span style={{fontSize:'10px',color:'var(--muted)'}}>{sessions.length} sessions</span>
            </div>
            {loadingSessions ? (
              <div className="chat-sessions-empty">Loading...</div>
            ) : sessions.length === 0 ? (
              <div className="chat-sessions-empty">No previous chats</div>
            ) : (
              <div className="chat-sessions-list">
                {sessions.map((s) => (
                  <div
                    key={s.session_id}
                    className={`chat-session-item ${sessionId === s.session_id ? 'active' : ''}`}
                    onClick={() => loadSession(s.session_id)}
                  >
                    <div className="chat-session-title">{s.title}</div>
                    <div className="chat-session-time">{formatTimeAgo(s.last_active)}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="chat-messages" style={{flex:1,overflowY:'auto',display:'flex',flexDirection:'column',gap:'16px',padding:'16px'}}>
        {messages.length === 0 && (
          <div className="msg ai">
             <div className="msg-role">AI Assistant</div>
             <div className="msg-bubble">
               I'm ready to help you research this company. Ask me anything about the financials, risks, business segments, or strategic direction based on the uploaded reports. I'll cite exactly where I found the information.
             </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`msg ${msg.role === 'user' ? 'user' : 'ai'}`}>
            <div className="msg-role">{msg.role === 'user' ? 'You' : 'AI Assistant'}</div>
            <div className="msg-bubble">
              <Markdown content={msg.content} />
              {msg.citations && msg.citations.length > 0 && (
                <div style={{marginTop:'8px', display:'flex', flexWrap:'wrap', gap:'6px'}}>
                  {msg.citations.map((c, j) => (
                    <span key={j} className="citation" title={c.snippet}>
                      § {c.document_name || 'Doc'}, p. {c.page_number ?? '?'}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="msg ai">
             <div className="msg-role">AI Assistant</div>
             <div className="msg-bubble">Analyzing the document...</div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <textarea
          className="chat-input"
          rows="1"
          placeholder="Ask about risks, growth drivers, financials..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
        />
        <button className="send-btn" onClick={() => handleSend()}><Send size={15} /></button>
      </div>
    </div>
  )
}
