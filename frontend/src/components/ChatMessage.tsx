import React, { useState } from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import confetti from 'canvas-confetti'
import {
  User,
  Sparkles,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  Zap,
  ShieldCheck,
  ExternalLink,
  BookOpen,
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
      if (rating === 'up') {
        confetti({
          particleCount: 30,
          spread: 45,
          origin: { y: 0.8 },
          colors: ['#3b82f6', '#10b981', '#6366f1'],
        })
      }
    }
  }

  const isUser = message.role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className={`flex gap-3 md:gap-4 p-4 md:p-5 rounded-xl transition-all ${
        isUser
          ? 'bg-slate-900/70 border border-slate-800 ml-auto max-w-[85%] md:max-w-[70%]'
          : 'bg-slate-900/30 border border-slate-800/80 mr-auto max-w-[95%] md:max-w-[85%] w-full'
      }`}
    >
      {/* Avatar */}
      <div className="shrink-0 mt-0.5">
        {isUser ? (
          <div className="w-7 h-7 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
            <User className="w-3.5 h-3.5" />
          </div>
        ) : (
          <div className="w-7 h-7 rounded-lg bg-blue-600/20 border border-blue-500/30 text-blue-400 flex items-center justify-center">
            <Sparkles className="w-3.5 h-3.5" />
          </div>
        )}
      </div>

      {/* Message Body */}
      <div className="flex-1 min-w-0 space-y-2.5">
        {/* Assistant Header (Clean & Minimal) */}
        {!isUser && (
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold text-slate-200">Assistant</span>

            {message.provider_used && message.provider_used.includes('cache') && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20 flex items-center gap-1">
                <Zap className="w-3 h-3" />
                Instant Answer
              </span>
            )}

            {message.corrections && message.corrections.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" />
                Verified Grounded
              </span>
            )}

            {message.latency && (
              <span className="text-[10px] text-slate-500 ml-auto font-mono">
                {message.latency.toFixed(2)}s
              </span>
            )}
          </div>
        )}

        {/* Markdown Content */}
        <div className="text-slate-200 text-sm leading-relaxed prose prose-invert max-w-none prose-p:my-2 prose-headings:my-3 prose-pre:my-2 prose-pre:bg-slate-950 prose-pre:border prose-pre:border-slate-800/80">
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
                        className="inline-flex items-center justify-center px-1.5 py-0.2 mx-0.5 rounded bg-blue-500/15 hover:bg-blue-500/30 text-blue-300 font-medium text-[11px] border border-blue-500/30 transition-colors"
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
                    className="text-blue-400 hover:text-blue-300 underline inline-flex items-center gap-0.5"
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
            <span className="inline-block w-1.5 h-3.5 ml-1 bg-blue-400 animate-pulse align-middle rounded-sm" />
          )}
        </div>

        {/* Verified Sources Pill List */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="pt-2 border-t border-slate-800/60 mt-2">
            <span className="text-[11px] font-medium text-slate-400 block mb-1.5 flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-blue-400" />
              Referenced Sources ({message.citations.length})
            </span>
            <div className="flex flex-wrap gap-1.5">
              {message.citations.map((cit) => (
                <button
                  key={cit.index}
                  onClick={() => onSelectCitation(cit)}
                  className="px-2.5 py-1 rounded-md bg-slate-900 hover:bg-slate-850 text-slate-300 border border-slate-800 hover:border-slate-700 text-xs flex items-center gap-1.5 transition-colors"
                >
                  <span className="w-4 h-4 rounded bg-blue-500/15 text-blue-400 flex items-center justify-center text-[10px] font-bold">
                    {cit.index}
                  </span>
                  <span className="max-w-[220px] truncate text-slate-300">{cit.source}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Bottom Actions for Assistant Message */}
        {!isUser && !message.isStreaming && (
          <div className="flex items-center justify-between pt-1 text-slate-400 text-xs">
            <div className="flex items-center gap-2">
              <button
                onClick={handleCopy}
                className="px-2 py-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1 text-xs"
                title="Copy response to clipboard"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span className="text-[11px]">{copied ? 'Copied' : 'Copy'}</span>
              </button>

              <div className="flex items-center gap-1 ml-1 border-l border-slate-800 pl-2">
                <button
                  onClick={() => handleFeedback('up')}
                  disabled={feedbackGiven !== null}
                  className={`p-1 rounded transition-colors ${
                    feedbackGiven === 'up'
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'hover:bg-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                  title="Accurate and helpful"
                >
                  <ThumbsUp className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => handleFeedback('down')}
                  disabled={feedbackGiven !== null}
                  className={`p-1 rounded transition-colors ${
                    feedbackGiven === 'down'
                      ? 'bg-rose-500/20 text-rose-400'
                      : 'hover:bg-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                  title="Inaccurate or unhelpful"
                >
                  <ThumbsDown className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}
