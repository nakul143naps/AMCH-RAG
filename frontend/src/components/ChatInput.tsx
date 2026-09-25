import React, { useState, useRef, useEffect } from 'react'
import { ArrowUp, StopCircle, Paperclip } from 'lucide-react'

interface ChatInputProps {
  onSendMessage: (query: string) => void
  isLoading: boolean
  onStop?: () => void
  onUploadFile?: (file: File) => Promise<void>
}

const SUGGESTIONS = [
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
    <div className="p-4 md:p-6 bg-gradient-to-t from-[#0f1117] via-[#0f1117]/90 to-transparent sticky bottom-0 z-20">
      <div className="max-w-3xl mx-auto space-y-3">
        {/* Suggestion Chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs no-scrollbar">
          {SUGGESTIONS.map((sug, idx) => (
            <button
              key={idx}
              type="button"
              disabled={isLoading}
              onClick={() => onSendMessage(sug)}
              className="px-3 py-1 rounded-full bg-zinc-900/90 hover:bg-zinc-800 text-zinc-300 border border-white/5 text-xs whitespace-nowrap transition-colors shrink-0 disabled:opacity-50"
            >
              {sug}
            </button>
          ))}
        </div>

        {/* Input Card */}
        <form
          onSubmit={handleSubmit}
          className="relative rounded-2xl bg-zinc-900/90 border border-white/10 focus-within:border-violet-500/60 focus-within:ring-2 focus-within:ring-violet-500/20 transition-all shadow-lg"
        >
          <textarea
            ref={textareaRef}
            rows={1}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Message Aura... ask anything about your documents or roadmap"
            className="w-full pl-11 pr-14 py-3.5 rounded-2xl bg-transparent text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none resize-none max-h-44 leading-relaxed"
          />

          {/* Left Attachment Icon */}
          <div className="absolute left-3 bottom-3 flex items-center">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading || isUploading}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors disabled:opacity-40"
              title="Attach and index document (PDF, TXT, DOCX)"
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
                className="w-8 h-8 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-400 flex items-center justify-center transition-colors"
                title="Stop response"
              >
                <StopCircle className="w-4 h-4 animate-pulse" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!query.trim()}
                className="w-8 h-8 rounded-xl bg-violet-600 hover:bg-violet-500 text-white flex items-center justify-center transition-all disabled:opacity-30 disabled:cursor-not-allowed shadow-md shadow-violet-600/20"
                title="Send message"
              >
                <ArrowUp className="w-4 h-4" />
              </button>
            )}
          </div>
        </form>

        <div className="text-center text-[11px] text-zinc-500">
          Personal AI Companion &bull; Grounded in your uploaded knowledge
        </div>
      </div>
    </div>
  )
}
