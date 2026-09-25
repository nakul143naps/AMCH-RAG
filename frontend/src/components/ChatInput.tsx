import React, { useState, useRef, useEffect } from 'react'
import { ArrowUp, StopCircle, Paperclip } from 'lucide-react'

interface ChatInputProps {
  onSendMessage: (query: string) => void
  isLoading: boolean
  onStop?: () => void
  onUploadFile?: (file: File) => Promise<void>
}

const DEFAULT_SUGGESTIONS = [
  'Summarize the AI Engineer roadmap',
  'What are the 9 clusters in the guide?',
  'Explain transfer learning in detail',
  'What is the standard starting dosage of lisinopril?',
]

export const ChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  isLoading,
  onStop,
  onUploadFile,
}) => {
  const [query, setQuery] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`
    }
  }, [query])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || isLoading) return
    onSendMessage(query.trim())
    setQuery('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !onUploadFile) return
    setIsUploading(true)
    try {
      await onUploadFile(file)
    } finally {
      setIsUploading(false)
      e.target.value = ''
    }
  }

  return (
    <div className="p-3 md:p-5 bg-gradient-to-t from-[#f8fafc] via-[#f8fafc]/95 to-transparent sticky bottom-0 z-20">
      <div className="max-w-3xl mx-auto space-y-2.5">
        {/* Suggestion Chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 text-xs no-scrollbar">
          {DEFAULT_SUGGESTIONS.map((sug, idx) => (
            <button
              key={idx}
              type="button"
              disabled={isLoading}
              onClick={() => onSendMessage(sug)}
              className="px-3 py-1 rounded-full bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-xs text-xs whitespace-nowrap transition-colors shrink-0 disabled:opacity-50 cursor-pointer"
            >
              {sug}
            </button>
          ))}
        </div>

        {/* Input Box (ChatGPT style) */}
        <form
          onSubmit={handleSubmit}
          className="relative rounded-2xl bg-white border border-slate-200/90 focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-100 transition-all shadow-xs"
        >
          <textarea
            ref={textareaRef}
            rows={1}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Ask AMCH-RAG anything... (Shift+Enter for new line)"
            className="w-full pl-11 pr-14 py-3.5 rounded-2xl bg-transparent text-sm text-slate-900 placeholder-slate-400 focus:outline-none resize-none max-h-44 leading-relaxed"
          />

          {/* Left Attachment Icon */}
          <div className="absolute left-3 bottom-3 flex items-center">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading || isUploading}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-40 cursor-pointer"
              title="Index new document (PDF, TXT, DOCX)"
            >
              <Paperclip className="w-4 h-4" />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleFileChange}
              className="hidden"
              accept=".pdf,.docx,.txt,.md,.csv"
            />
          </div>

          {/* Right Action Button (Send / Stop) */}
          <div className="absolute right-2.5 bottom-2.5 flex items-center gap-1">
            {isLoading ? (
              <button
                type="button"
                onClick={onStop}
                className="w-8 h-8 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-600 flex items-center justify-center transition-colors cursor-pointer"
                title="Stop response"
              >
                <StopCircle className="w-4 h-4 animate-pulse" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!query.trim()}
                className="w-8 h-8 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center transition-all disabled:opacity-30 disabled:cursor-not-allowed shadow-xs cursor-pointer"
                title="Send message"
              >
                <ArrowUp className="w-4 h-4" />
              </button>
            )}
          </div>
        </form>

        <div className="text-center text-[11px] text-slate-400 font-medium">
          AMCH-RAG: Agentic Multi-Modal Corrective Hybrid RAG &bull; Verified Grounded Citations
        </div>
      </div>
    </div>
  )
}
