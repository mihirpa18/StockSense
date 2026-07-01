import { useState } from 'react'
import { Send } from 'lucide-react'

export default function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!value.trim() || disabled) return
    onSend(value.trim())
    setValue('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 px-4 py-3 border-t border-white/[0.06]">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask about the report..."
        disabled={disabled}
        className="flex-1 input-glass !py-2.5 !text-sm"
        id="chat-input"
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="btn-primary !px-3 !py-2.5 disabled:opacity-30"
        id="chat-send-btn"
      >
        <Send size={16} />
      </button>
    </form>
  )
}
