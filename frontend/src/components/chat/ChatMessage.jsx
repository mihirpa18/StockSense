import { Bot, User, FileText } from 'lucide-react'

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 animate-fade-in ${isUser ? 'justify-end' : ''}`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-xl shrink-0 flex items-center justify-center mt-0.5" style={{ background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)' }}>
          <Bot size={14} className="text-white" />
        </div>
      )}

      <div className={`max-w-[85%] ${isUser ? 'order-first' : ''}`}>
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? 'bg-blue-600/20 border border-blue-500/20 text-gray-100 rounded-br-md'
              : message.error
              ? 'glass-1 text-red-300 border-red-500/20'
              : 'glass-1 text-gray-200 rounded-bl-md'
          }`}
        >
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 space-y-1">
            <p className="text-[10px] text-gray-600 uppercase tracking-wider font-medium px-1">Sources</p>
            {message.citations.map((cite, i) => (
              <div key={i} className="flex items-start gap-2 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                <FileText size={12} className="text-blue-400/60 mt-0.5 shrink-0" />
                <div>
                  <span className="text-xs font-mono text-blue-400/80">Page {cite.page_number}</span>
                  <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{cite.snippet}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-xl shrink-0 flex items-center justify-center mt-0.5 glass-1">
          <User size={14} className="text-gray-400" />
        </div>
      )}
    </div>
  )
}
