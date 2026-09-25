import React, { useState, useRef, useEffect } from 'react'
import { Send, Sparkles, StopCircle } from 'lucide-react'

interface ChatInputProps {
  onSendMessage: (query: string) => void
  isLoading: boolean
  onStop?: () => void
}

const SUGGESTIONS = [
  'What are the 9 clusters mentioned in the roadmap?',
  'Explain inductive transfer learning',
  'Who wrote Romeo and Juliet?',
  'What is the standard starting dosage of lisinopril?',
]

export const ChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  isLoading,
  onStop,
}) => {
  const [query, setQuery] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`
    }
  }, [query])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || isLoading) return
    onSendMessage(query.trim())
    setQuery('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="p-4 md:p-6 bg-gradient-to-t from-slate-950 via-slate-950/90 to-transparent sticky bottom-0 z-20">
      <div className="max-w-4xl mx-auto space-y-3">
        {/* Suggestion Chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs no-scrollbar">
          <span className="text-slate-500 font-medium shrink-0 flex items-center gap-1 pl-1">
            <Sparkles className="w-3 h-3 text-blue-400" />
            Try:
          </span>
          {SUGGESTIONS.map((sug, idx) => (
            <button
              key={idx}
              type="button"
              disabled={isLoading}
              onClick={() => onSendMessage(sug)}
              className="px-2.5 py-1 rounded-full bg-slate-900/80 hover:bg-slate-800 text-slate-300 border border-slate-800 hover:border-slate-700 text-[11px] whitespace-nowrap transition-all hover:scale-102 shrink-0 disabled:opacity-50"
            >
              {sug}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <form
          onSubmit={handleSubmit}
          className="relative rounded-2xl glass-panel border border-slate-700/80 focus-within:border-blue-500/80 focus-within:ring-2 focus-within:ring-blue-500/20 transition-all shadow-xl"
        >
          <textarea
            ref={textareaRef}
            rows={1}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Ask a question about roadmaps, documents, AI concepts, or general facts..."
            className="w-full pl-4 pr-14 py-3.5 rounded-2xl bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none resize-none max-h-40 leading-relaxed"
          />

          <div className="absolute right-2.5 bottom-2.5 flex items-center gap-1">
            {isLoading ? (
              <button
                type="button"
                onClick={onStop}
                className="w-8 h-8 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-400 flex items-center justify-center transition-colors"
                title="Stop generation"
              >
                <StopCircle className="w-4 h-4 animate-pulse" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!query.trim()}
                className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white flex items-center justify-center transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-md shadow-blue-500/20"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </form>

        <p className="text-center text-[10px] text-slate-500">
          AMCH-RAG uses Self-RAG & CRAG verification to prevent hallucinations &bull; Shift + Enter for new line
        </p>
      </div>
    </div>
  )
}
