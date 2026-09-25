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
          ? 'bg-indigo-600 text-white ml-auto max-w-[85%] md:max-w-[75%] shadow-sm'
          : 'bg-white border border-slate-200 text-slate-800 mr-auto max-w-[95%] md:max-w-[85%] w-full shadow-sm'
      }`}
    >
      {/* Avatar for Assistant */}
      {!isUser && (
        <div className="shrink-0 mt-1">
          <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-indigo-500 to-violet-600 flex items-center justify-center text-white shadow-xs">
            <Sparkles className="w-3.5 h-3.5" />
          </div>
        </div>
      )}

      {/* Message Body */}
      <div className="flex-1 min-w-0 space-y-2">
        {!isUser && (
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
            <span>Aura</span>
          </div>
        )}

        {/* Markdown Content */}
        <div className={`text-sm leading-relaxed ${isUser ? 'text-white' : 'text-slate-800'} prose max-w-none prose-p:my-1.5 prose-headings:my-2 prose-pre:my-2 prose-pre:bg-slate-900 prose-pre:text-slate-100 prose-pre:border prose-pre:border-slate-800`}>
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
                        className="inline-flex items-center justify-center px-1.5 py-0.2 mx-0.5 rounded-full bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold text-[11px] border border-indigo-200 transition-colors cursor-pointer"
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
                    className="text-indigo-600 hover:text-indigo-700 underline inline-flex items-center gap-0.5"
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
            <span className="inline-block w-1.5 h-3.5 ml-1 bg-indigo-600 animate-pulse align-middle rounded-full" />
          )}
        </div>

        {/* Referenced Sources Footer */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="pt-2.5 border-t border-slate-100 mt-3">
            <span className="text-[11px] text-slate-500 block mb-1.5 flex items-center gap-1.5 font-medium">
              <BookOpen className="w-3.5 h-3.5 text-indigo-500" />
              Sources Referenced ({message.citations.length})
            </span>
            <div className="flex flex-wrap gap-1.5">
              {message.citations.map((cit) => (
                <button
                  key={cit.index}
                  onClick={() => onSelectCitation(cit)}
                  className="px-2.5 py-1 rounded-full bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 hover:border-slate-300 text-xs flex items-center gap-1.5 transition-all cursor-pointer"
                >
                  <span className="w-4 h-4 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-[10px] font-bold">
                    {cit.index}
                  </span>
                  <span className="max-w-[200px] truncate text-slate-700">{cit.source}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Action Toolbar for Assistant */}
        {!isUser && !message.isStreaming && (
          <div className="flex items-center gap-2 pt-1 text-slate-400 text-xs">
            <button
              onClick={handleCopy}
              className="p-1 rounded-md hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition-colors flex items-center gap-1 text-xs cursor-pointer"
              title="Copy answer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span className="text-[11px]">{copied ? 'Copied' : 'Copy'}</span>
            </button>

            <button
              onClick={() => handleFeedback('up')}
              disabled={feedbackGiven !== null}
              className={`p-1 rounded-md transition-colors cursor-pointer ${
                feedbackGiven === 'up'
                  ? 'bg-emerald-50 text-emerald-600'
                  : 'hover:bg-slate-100 text-slate-400 hover:text-slate-700'
              }`}
              title="Helpful"
            >
              <ThumbsUp className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={() => handleFeedback('down')}
              disabled={feedbackGiven !== null}
              className={`p-1 rounded-md transition-colors cursor-pointer ${
                feedbackGiven === 'down'
                  ? 'bg-rose-50 text-rose-600'
                  : 'hover:bg-slate-100 text-slate-400 hover:text-slate-700'
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
