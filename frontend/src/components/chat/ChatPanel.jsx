import { useState, useRef, useEffect } from 'react'
import { sendChat } from '../../lib/api'
import Markdown from '../ui/Markdown'

export default function ChatPanel({ companyId, documentId }) {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    setMessages([])
    setSessionId(null)
  }, [companyId, documentId])

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

  return (
    <div style={{display:'flex',flexDirection:'column',height:'100%'}}>
      <div className="chat-header">
        <div className="ai-dot"></div>
        AI Research Assistant
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
        <button className="send-btn" onClick={() => handleSend()}>↑</button>
      </div>
    </div>
  )
}
