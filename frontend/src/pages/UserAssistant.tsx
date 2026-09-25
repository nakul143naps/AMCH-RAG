import React, { useState, useEffect, useRef } from 'react'
import { UserHeader } from '../components/UserHeader'
import { ChatMessage } from '../components/ChatMessage'
import { ChatInput } from '../components/ChatInput'
import { CitationDrawer } from '../components/CitationDrawer'
import type { Message, Citation } from '../types'
import { Sparkles, Compass, BookOpen, ShieldCheck } from 'lucide-react'

export const UserAssistant: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([])
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>(() => `user_sess_${Date.now()}`)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = async (queryText: string) => {
    if (!queryText.trim() || isLoading) return

    const userMsgId = `msg_${Date.now()}`
    const assistantMsgId = `msg_${Date.now() + 1}`

    const userMsg: Message = {
      id: userMsgId,
      role: 'user',
      content: queryText,
      timestamp: new Date().toLocaleTimeString(),
    }

    const initialAssistantMsg: Message = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toLocaleTimeString(),
      citations: [],
      corrections: [],
      isStreaming: true,
    }

    setMessages((prev) => [...prev, userMsg, initialAssistantMsg])
    setIsLoading(true)

    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch('/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          query: queryText,
          session_id: sessionId,
          user_id: 'public_user',
          stream: true,
        }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''
      const collectedCitations: Citation[] = []
      const collectedCorrections: string[] = []
      let traceId = ''
      let providerUsed = ''
      let streamBuffer = ''

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          streamBuffer += decoder.decode(value, { stream: true })
          const lines = streamBuffer.split('\n')
          streamBuffer = lines.pop() || ''

          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed || !trimmed.startsWith('data:')) continue

            const jsonStr = trimmed.slice(5).trim()
            if (!jsonStr) continue

            try {
              const payload = JSON.parse(jsonStr)

              if (payload.type === 'token') {
                fullContent += payload.token || ''
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMsgId ? { ...msg, content: fullContent } : msg
                  )
                )
              } else if (payload.type === 'citation') {
                const cit: Citation = {
                  index: payload.index || collectedCitations.length + 1,
                  source: payload.source || 'Knowledge Base',
                  chunk_id: payload.chunk_id || '',
                  page: payload.page,
                  section: payload.section,
                  content: payload.content,
                }
                collectedCitations.push(cit)
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMsgId
                      ? { ...msg, citations: [...collectedCitations] }
                      : msg
                  )
                )
              } else if (payload.type === 'correction') {
                collectedCorrections.push(payload.message || 'Groundedness verified')
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMsgId
                      ? { ...msg, corrections: [...collectedCorrections] }
                      : msg
                  )
                )
              } else if (payload.type === 'done') {
                traceId = payload.trace_id || ''
                providerUsed = payload.provider_used || ''
                if (payload.citations && payload.citations.length > 0) {
                  payload.citations.forEach((c: any, i: number) => {
                    if (!collectedCitations.some((existing) => existing.chunk_id === c.chunk_id)) {
                      collectedCitations.push({
                        index: c.index || i + 1,
                        source: c.source || 'Knowledge Base',
                        chunk_id: c.chunk_id || '',
                        page: c.page,
                        section: c.section,
                        content: c.content,
                      })
                    }
                  })
                }
              }
            } catch (err) {
              console.warn('Malformed SSE event chunk:', err)
            }
          }
        }
      }

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                content: fullContent,
                isStreaming: false,
                citations: collectedCitations,
                corrections: collectedCorrections,
                trace_id: traceId,
                provider_used: providerUsed,
              }
            : msg
        )
      )
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error('Query streaming error:', err)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? {
                  ...msg,
                  content:
                    'I encountered an error retrieving or validating information from the knowledge base. Please try again or rephrase your question.',
                  isStreaming: false,
                }
              : msg
          )
        )
      }
    } finally {
      setIsLoading(false)
      abortControllerRef.current = null
    }
  }

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      setIsLoading(false)
    }
  }

  const handleFeedback = async (traceId: string, rating: 'up' | 'down') => {
    try {
      await fetch('/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trace_id: traceId, rating }),
      })
    } catch (e) {
      console.error('Feedback dispatch error:', e)
    }
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#090d16] font-sans text-slate-100">
      <div className="flex-1 flex flex-col min-w-0 h-full relative">
        {/* Clean Public Header */}
        <UserHeader
          onResetSession={() => {
            setSessionId(`user_sess_${Date.now()}`)
            setMessages([])
          }}
        />

        {/* Public Chat Feed */}
        <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-4">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-2xl mx-auto py-12">
              <div className="w-12 h-12 rounded-xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center text-blue-400 mb-5 shadow-sm">
                <Sparkles className="w-6 h-6" />
              </div>
              <h2 className="text-xl md:text-2xl font-bold tracking-tight text-white mb-2">
                How can I assist you today?
              </h2>
              <p className="text-xs md:text-sm text-slate-400 leading-relaxed mb-8 max-w-lg">
                Ask questions about your uploaded documents, roadmaps, systems, or technical concepts. Every response is strictly grounded in verified facts.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full text-left">
                <button
                  onClick={() => handleSendMessage('Summarize the 9 AI Engineer clusters in the roadmap')}
                  className="p-4 rounded-xl bg-slate-900/60 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all text-left group"
                >
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-300 group-hover:text-blue-400 mb-1">
                    <Compass className="w-4 h-4 text-blue-400" />
                    <span>Roadmap Clusters</span>
                  </div>
                  <p className="text-[11px] text-slate-500 leading-normal">
                    Explore the 9 key clusters from the AI Engineer Field Guide
                  </p>
                </button>

                <button
                  onClick={() => handleSendMessage('Explain inductive vs transductive transfer learning in detail')}
                  className="p-4 rounded-xl bg-slate-900/60 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all text-left group"
                >
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-300 group-hover:text-purple-400 mb-1">
                    <BookOpen className="w-4 h-4 text-purple-400" />
                    <span>Transfer Learning</span>
                  </div>
                  <p className="text-[11px] text-slate-500 leading-normal">
                    Deep dive into fine-tuning, inductive, and domain adaptation
                  </p>
                </button>

                <button
                  onClick={() => handleSendMessage('What is the standard starting dosage of lisinopril?')}
                  className="p-4 rounded-xl bg-slate-900/60 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all text-left group"
                >
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-300 group-hover:text-emerald-400 mb-1">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    <span>Precision Answers</span>
                  </div>
                  <p className="text-[11px] text-slate-500 leading-normal">
                    Fact-checked clinical reference or general factual queries
                  </p>
                </button>
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-4">
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  onSelectCitation={(cit) => setSelectedCitation(cit)}
                  onFeedback={handleFeedback}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Public Chat Input */}
        <ChatInput
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          onStop={handleStop}
        />
      </div>

      {/* Slide-Over Verified Citation Drawer */}
      <CitationDrawer
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  )
}
