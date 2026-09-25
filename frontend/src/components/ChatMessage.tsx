import React, { useState } from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import confetti from 'canvas-confetti'
import {
  User,
  Bot,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  Sparkles,
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
          particleCount: 40,
          spread: 50,
          origin: { y: 0.8 },
          colors: ['#3b82f6', '#10b981', '#a855f7'],
        })
      }
    }
  }

  const isUser = message.role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className={`flex gap-3 md:gap-4 p-4 md:p-6 rounded-2xl transition-all ${
        isUser
          ? 'bg-slate-900/60 border border-slate-800/80 ml-auto max-w-[85%] md:max-w-[75%]'
          : 'glass-panel border border-slate-800/80 mr-auto max-w-[95%] md:max-w-[85%] w-full'
      }`}
    >
      {/* Avatar */}
      <div className="shrink-0 mt-0.5">
        {isUser ? (
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-slate-700 to-slate-600 flex items-center justify-center text-slate-200 shadow-md">
            <User className="w-4 h-4" />
          </div>
        ) : (
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-purple-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
            <Bot className="w-4 h-4" />
          </div>
        )}
      </div>

      {/* Message Content */}
      <div className="flex-1 min-w-0 space-y-2.5">
        {/* Header Metadata for Assistant */}
        {!isUser && (
          <div className="flex flex-wrap items-center gap-2 pb-1 border-b border-slate-800/60 text-xs">
            <span className="font-semibold text-slate-200">AMCH-RAG Assistant</span>

            {/* Provider / Route Badges */}
            {message.provider_used && (
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border flex items-center gap-1 ${
                  message.provider_used.includes('cache')
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                    : 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                }`}
              >
                {message.provider_used.includes('cache') ? (
                  <Zap className="w-3 h-3" />
                ) : (
                  <Sparkles className="w-3 h-3" />
                )}
                {message.provider_used.toUpperCase()}
              </span>
            )}

            {message.latency && (
              <span className="text-[10px] text-slate-400">
                {message.latency.toFixed(2)}s
              </span>
            )}

            {/* Self-RAG / CRAG corrections */}
            {message.corrections && message.corrections.length > 0 && (
              <div className="flex items-center gap-1.5 ml-auto">
                {message.corrections.map((corr, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-medium flex items-center gap-1"
                  >
                    <ShieldCheck className="w-3 h-3" />
                    {corr}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Markdown Render */}
        <div className="text-slate-200 text-sm leading-relaxed prose prose-invert max-w-none prose-pre:bg-slate-950/80 prose-pre:border prose-pre:border-slate-800">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // Custom citation link render (e.g. [1], [2])
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
                        className="inline-flex items-center justify-center px-1.5 py-0.5 mx-0.5 rounded bg-blue-500/20 hover:bg-blue-500/40 text-blue-300 font-semibold text-[11px] border border-blue-500/40 transition-colors"
                        title={`View Source: ${matchedCit.source}`}
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
                    className="text-blue-400 hover:underline inline-flex items-center gap-0.5"
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
            <span className="inline-block w-2 h-4 ml-1 bg-blue-400 animate-pulse-dot align-middle" />
          )}
        </div>

        {/* Citations Footer Section */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="pt-2 border-t border-slate-800/60">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5 flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-purple-400" />
              Verified Citations ({message.citations.length})
            </span>
            <div className="flex flex-wrap gap-1.5">
              {message.citations.map((cit) => (
                <button
                  key={cit.index}
                  onClick={() => onSelectCitation(cit)}
                  className="px-2.5 py-1 rounded-lg bg-slate-900/80 hover:bg-slate-800 text-slate-300 border border-slate-700/60 text-xs font-medium flex items-center gap-1.5 transition-all hover:scale-102"
                >
                  <span className="w-4 h-4 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-[10px] font-bold">
                    {cit.index}
                  </span>
                  <span className="max-w-[200px] truncate">{cit.source}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Action Toolbar for Assistant */}
        {!isUser && (
          <div className="flex items-center justify-between pt-1 text-slate-400 text-xs">
            <div className="flex items-center gap-2">
              <button
                onClick={handleCopy}
                className="p-1 rounded-md hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1"
                title="Copy response"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span className="text-[11px]">{copied ? 'Copied' : 'Copy'}</span>
              </button>

              <div className="flex items-center gap-1 ml-2 border-l border-slate-800 pl-2">
                <button
                  onClick={() => handleFeedback('up')}
                  disabled={feedbackGiven !== null}
                  className={`p-1 rounded-md transition-colors ${
                    feedbackGiven === 'up'
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'hover:bg-slate-800 text-slate-400 hover:text-slate-200'
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
                      : 'hover:bg-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                  title="Unhelpful"
                >
                  <ThumbsDown className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {message.trace_id && (
              <span className="text-[10px] text-slate-500 font-mono">
                Trace: {message.trace_id.slice(0, 8)}...
              </span>
            )}
          </div>
        )}
      </div>
    </motion.div>
  )
}
