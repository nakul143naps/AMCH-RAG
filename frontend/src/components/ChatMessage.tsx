import React, { useState } from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Sparkles,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  BookOpen,
  ExternalLink,
} from 'lucide-react'
import type { Message, Citation } from '../types'

interface ChatMessageProps {
  message: Message
  onSelectCitation: (citation: Citation) => void
  onFeedback: (traceId: string, rating: 'up' | 'down') => void
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  onSelectCitation,
  onFeedback,
}) => {
  const [copied, setCopied] = useState(false)
  const [feedbackGiven, setFeedbackGiven] = useState<'up' | 'down' | null>(null)

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleFeedback = (rating: 'up' | 'down') => {
    if (message.trace_id && !feedbackGiven) {
      onFeedback(message.trace_id, rating)
      setFeedbackGiven(rating)
    }
  }

  const isUser = message.role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className={`flex gap-3 md:gap-4 p-4 rounded-2xl transition-all ${
        isUser
          ? 'bg-violet-600/90 text-white ml-auto max-w-[85%] md:max-w-[75%] shadow-md shadow-violet-600/10'
          : 'soft-card mr-auto max-w-[95%] md:max-w-[85%] w-full text-zinc-100'
      }`}
    >
      {/* Avatar for Assistant */}
      {!isUser && (
        <div className="shrink-0 mt-1">
          <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-violet-600 to-indigo-500 flex items-center justify-center text-white shadow-sm">
            <Sparkles className="w-3.5 h-3.5" />
          </div>
        </div>
      )}

      {/* Message Body */}
      <div className="flex-1 min-w-0 space-y-2">
        {!isUser && (
          <div className="flex items-center gap-2 text-xs font-medium text-zinc-400">
            <span>Aura</span>
          </div>
        )}

        {/* Markdown Content */}
        <div className={`text-sm leading-relaxed ${isUser ? 'text-white' : 'text-zinc-200'} prose prose-invert max-w-none prose-p:my-1.5 prose-headings:my-2 prose-pre:my-2 prose-pre:bg-zinc-950 prose-pre:border prose-pre:border-white/5`}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a: ({ href, children }) => {
                const text = String(children)
                const citMatch = text.match(/^\[(\d+)\]$/)
                if (citMatch && message.citations) {
                  const idx = parseInt(citMatch[1], 10)
                  const matchedCit = message.citations.find((c) => c.index === idx)
                  if (matchedCit) {
                    return (
                      <button
                        onClick={() => onSelectCitation(matchedCit)}
                        className="inline-flex items-center justify-center px-1.5 py-0.2 mx-0.5 rounded-full bg-violet-500/20 hover:bg-violet-500/35 text-violet-300 font-medium text-[11px] border border-violet-500/30 transition-colors"
                        title={`Source: ${matchedCit.source}`}
                      >
                        [{idx}]
                      </button>
                    )
                  }
                }
                return (
                  <a
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    className="text-violet-400 hover:text-violet-300 underline inline-flex items-center gap-0.5"
                  >
                    {children}
                    <ExternalLink className="w-3 h-3 opacity-60 inline" />
                  </a>
                )
              },
            }}
          >
            {message.content}
          </ReactMarkdown>

          {message.isStreaming && (
            <span className="inline-block w-1.5 h-3.5 ml-1 bg-violet-400 animate-pulse align-middle rounded-full" />
          )}
        </div>

        {/* Referenced Sources Footer */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="pt-2 border-t border-white/5 mt-3">
            <span className="text-[11px] text-zinc-400 block mb-1.5 flex items-center gap-1.5 font-medium">
              <BookOpen className="w-3.5 h-3.5 text-violet-400" />
              Sources Referenced ({message.citations.length})
            </span>
            <div className="flex flex-wrap gap-1.5">
              {message.citations.map((cit) => (
                <button
                  key={cit.index}
                  onClick={() => onSelectCitation(cit)}
                  className="px-2.5 py-1 rounded-full bg-zinc-900/80 hover:bg-zinc-800 text-zinc-300 border border-white/5 hover:border-white/15 text-xs flex items-center gap-1.5 transition-all"
                >
                  <span className="w-4 h-4 rounded-full bg-violet-500/20 text-violet-300 flex items-center justify-center text-[10px] font-bold">
                    {cit.index}
                  </span>
                  <span className="max-w-[200px] truncate text-zinc-300">{cit.source}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Action Toolbar for Assistant */}
        {!isUser && !message.isStreaming && (
          <div className="flex items-center gap-2 pt-1 text-zinc-400 text-xs">
            <button
              onClick={handleCopy}
              className="p-1 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors flex items-center gap-1 text-xs"
              title="Copy answer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span className="text-[11px]">{copied ? 'Copied' : 'Copy'}</span>
            </button>

            <button
              onClick={() => handleFeedback('up')}
              disabled={feedbackGiven !== null}
              className={`p-1 rounded-md transition-colors ${
                feedbackGiven === 'up'
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200'
              }`}
              title="Helpful"
            >
              <ThumbsUp className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={() => handleFeedback('down')}
              disabled={feedbackGiven !== null}
              className={`p-1 rounded-md transition-colors ${
                feedbackGiven === 'down'
                  ? 'bg-rose-500/20 text-rose-400'
                  : 'hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200'
              }`}
              title="Unhelpful"
            >
              <ThumbsDown className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </motion.div>
  )
}
