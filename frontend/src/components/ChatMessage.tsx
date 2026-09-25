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
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  Cpu,
  ArrowRight,
} from 'lucide-react'
import type { Message, Citation } from '../types'

interface ChatMessageProps {
  message: Message
  onSelectCitation: (citation: Citation) => void
  onFeedback: (traceId: string, rating: 'up' | 'down') => void
  onFollowUp?: (suggestion: string) => void
  isLast?: boolean
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  onSelectCitation,
  onFeedback,
  onFollowUp,
  isLast,
}) => {
  const [copied, setCopied] = useState(false)
  const [feedbackGiven, setFeedbackGiven] = useState<'up' | 'down' | null>(null)
  const [showTraceDetails, setShowTraceDetails] = useState(false)

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

  // Contextual follow-up suggestions for assistant responses
  const getFollowUpSuggestions = () => {
    const text = message.content.toLowerCase()
    if (text.includes('roadmap') || text.includes('engineer') || text.includes('cluster')) {
      return [
        'What are the key prerequisites for Cluster 1 and 2?',
        'How should I prioritize these clusters for production?',
        'Give a practical roadmap study timeline',
      ]
    }
    if (text.includes('transfer') || text.includes('inductive') || text.includes('transductive')) {
      return [
        'Can you show a PyTorch example of inductive transfer learning?',
        'What are the primary differences between fine-tuning and feature extraction?',
        'How does domain adaptation fit into this?',
      ]
    }
    if (text.includes('lisinopril') || text.includes('dosage') || text.includes('hypertension')) {
      return [
        'What are the common side effects and contraindications?',
        'What monitoring parameters are required for ACE inhibitors?',
        'How does dosage adjust for renal impairment?',
      ]
    }
    return [
      'Can you give a practical implementation example?',
      'What are the main advantages and trade-offs?',
      'Summarize the essential key takeaways',
    ]
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className={`flex gap-3 md:gap-4 p-4 md:p-5 rounded-2xl transition-all ${
        isUser
          ? 'bg-indigo-600 text-white ml-auto max-w-[85%] md:max-w-[75%] shadow-xs'
          : 'bg-white border border-slate-200/90 text-slate-800 mr-auto max-w-full md:max-w-[88%] w-full shadow-xs'
      }`}
    >
      {/* Avatar for Assistant */}
      {!isUser && (
        <div className="shrink-0 mt-0.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center text-white shadow-xs">
            <Sparkles className="w-4 h-4" />
          </div>
        </div>
      )}

      {/* Message Body */}
      <div className="flex-1 min-w-0 space-y-2.5">
        {/* Assistant Header & Retrieval Steps Indicator (ChatGPT style) */}
        {!isUser && (
          <div className="flex flex-wrap items-center justify-between gap-2 pb-1 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <span className="font-bold text-xs text-slate-900 tracking-tight">AMCH-RAG</span>
              <span className="text-[10px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200/70 px-1.5 py-0.2 rounded-md">
                Verified RAG
              </span>
            </div>

            {/* Retrieval / Grounding Pill */}
            {message.citations && message.citations.length > 0 && (
              <button
                onClick={() => setShowTraceDetails(!showTraceDetails)}
                className="inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-600 hover:text-indigo-600 bg-slate-50 hover:bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200 transition-colors cursor-pointer"
              >
                <ShieldCheck className="w-3 h-3 text-emerald-600" />
                <span>{message.citations.length} sources cited &bull; Grounded</span>
                {showTraceDetails ? (
                  <ChevronUp className="w-3 h-3 text-slate-400" />
                ) : (
                  <ChevronDown className="w-3 h-3 text-slate-400" />
                )}
              </button>
            )}
          </div>
        )}

        {/* Collapsible Retrieval & Verification Details */}
        {!isUser && showTraceDetails && (
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-2 animate-fadeIn">
            <div className="flex items-center justify-between text-slate-600 font-semibold text-[11px]">
              <span className="flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-indigo-600" />
                Retrieval Pipeline Trace
              </span>
              {message.provider_used && (
                <span className="px-1.5 py-0.5 rounded bg-white border border-slate-200 text-slate-700 text-[10px]">
                  Model: {message.provider_used}
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] text-slate-600">
              <div className="p-2 rounded-lg bg-white border border-slate-200">
                <span className="font-semibold text-slate-800 block">Hybrid Search</span>
                Dense (Qdrant Cosine) + Sparse (BM25) Fused
              </div>
              <div className="p-2 rounded-lg bg-white border border-slate-200">
                <span className="font-semibold text-slate-800 block">Verification &amp; Caching</span>
                Self-RAG Groundedness Gate &bull; L1/L2 Cache Active
              </div>
            </div>

            {message.corrections && message.corrections.length > 0 && (
              <div className="text-[11px] text-amber-700 bg-amber-50/80 p-2 rounded-lg border border-amber-200">
                <span className="font-semibold">Self-RAG Reflection:</span>{' '}
                {message.corrections.join(', ')}
              </div>
            )}
          </div>
        )}

        {/* Markdown Content */}
        <div
          className={`text-sm leading-relaxed ${
            isUser ? 'text-white' : 'text-slate-800'
          } prose max-w-none prose-p:my-1.5 prose-headings:my-2 prose-pre:my-2 prose-pre:bg-slate-900 prose-pre:text-slate-100 prose-pre:border prose-pre:border-slate-800`}
        >
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
          <div className="flex items-center justify-between pt-2 border-t border-slate-50 text-slate-400 text-xs">
            <div className="flex items-center gap-2">
              <button
                onClick={handleCopy}
                className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition-colors flex items-center gap-1 text-xs cursor-pointer"
                title="Copy answer"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                <span className="text-[11px] font-medium">{copied ? 'Copied' : 'Copy'}</span>
              </button>

              <button
                onClick={() => handleFeedback('up')}
                disabled={feedbackGiven !== null}
                className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
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
                className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                  feedbackGiven === 'down'
                    ? 'bg-rose-50 text-rose-600'
                    : 'hover:bg-slate-100 text-slate-400 hover:text-slate-700'
                }`}
                title="Unhelpful"
              >
                <ThumbsDown className="w-3.5 h-3.5" />
              </button>
            </div>

            {message.timestamp && (
              <span className="text-[10px] text-slate-400">{message.timestamp}</span>
            )}
          </div>
        )}

        {/* Dynamic Follow-Up Suggestions for the last assistant response (ChatGPT style) */}
        {!isUser && !message.isStreaming && isLast && onFollowUp && (
          <div className="pt-3 border-t border-slate-100 mt-2 space-y-1.5">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
              Suggested Follow-ups
            </span>
            <div className="flex flex-wrap gap-2">
              {getFollowUpSuggestions().map((suggestion, idx) => (
                <button
                  key={idx}
                  onClick={() => onFollowUp(suggestion)}
                  className="px-3 py-1.5 rounded-xl bg-slate-50 hover:bg-indigo-50/70 text-slate-700 hover:text-indigo-700 border border-slate-200 hover:border-indigo-200 text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer group"
                >
                  <span>{suggestion}</span>
                  <ArrowRight className="w-3 h-3 text-slate-400 group-hover:text-indigo-600 transition-colors" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}
