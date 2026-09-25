import React, { useState, useEffect, useRef } from 'react'
import { UserHeader } from '../components/UserHeader'
import { ChatMessage } from '../components/ChatMessage'
import { ChatInput } from '../components/ChatInput'
import { CitationDrawer } from '../components/CitationDrawer'
import type { Message, Citation } from '../types'
import { Sparkles, Compass, BookOpen, Heart } from 'lucide-react'

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
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    const initialAssistantMsg: Message = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
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
          user_id: 'personal_user',
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
                // Support both payload.content and payload.token
                const chunk = payload.content ?? payload.token ?? ''
                fullContent += chunk
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
                const reason = payload.reason || payload.message || 'Groundedness verified'
                collectedCorrections.push(reason)
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
              } else if (payload.type === 'error') {
                fullContent = `Notice: ${payload.detail || 'Could not process query'}`
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMsgId ? { ...msg, content: fullContent } : msg
                  )
                )
              }
            } catch (err) {
              console.warn('SSE chunk parsing warning:', err)
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
                  content: 'Sorry, I ran into an issue finding that answer. Please try asking again!',
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
      console.error('Feedback error:', e)
    }
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0f1117] font-sans text-zinc-100">
      <div className="flex-1 flex flex-col min-w-0 h-full relative">
        {/* Personal Assistant Header */}
        <UserHeader
          onResetSession={() => {
            setSessionId(`user_sess_${Date.now()}`)
            setMessages([])
          }}
        />

        {/* Chat Feed */}
        <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-4">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-xl mx-auto py-12">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-violet-600 to-indigo-500 flex items-center justify-center text-white mb-5 shadow-lg shadow-violet-500/20">
                <Sparkles className="w-7 h-7" />
              </div>
              <h2 className="text-2xl font-bold tracking-tight text-white mb-2">
                Hi there! What can I help you learn today?
              </h2>
              <p className="text-xs md:text-sm text-zinc-400 leading-relaxed mb-8 max-w-md">
                I am your personal knowledge assistant. Ask me questions about your uploaded documents, study roadmaps, or any concept you want to master.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full text-left">
                <button
                  onClick={() => handleSendMessage('Summarize the 9 AI Engineer clusters in the roadmap')}
                  className="p-4 rounded-xl soft-card hover:bg-zinc-800/80 transition-all text-left group"
                >
                  <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200 group-hover:text-violet-400 mb-1">
                    <Compass className="w-4 h-4 text-violet-400" />
                    <span>Study Roadmap</span>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-normal">
                    Explore the 9 key clusters from the AI Engineer guide
                  </p>
                </button>

                <button
                  onClick={() => handleSendMessage('Explain inductive vs transductive transfer learning in detail')}
                  className="p-4 rounded-xl soft-card hover:bg-zinc-800/80 transition-all text-left group"
                >
                  <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200 group-hover:text-violet-400 mb-1">
                    <BookOpen className="w-4 h-4 text-violet-400" />
                    <span>Transfer Learning</span>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-normal">
                    Deep dive into fine-tuning, inductive, and adaptation
                  </p>
                </button>

                <button
                  onClick={() => handleSendMessage('What is the standard starting dosage of lisinopril?')}
                  className="p-4 rounded-xl soft-card hover:bg-zinc-800/80 transition-all text-left group"
                >
                  <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200 group-hover:text-violet-400 mb-1">
                    <Heart className="w-4 h-4 text-violet-400" />
                    <span>Quick Facts</span>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-normal">
                    Ask quick fact-checked questions or clinical references
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

        {/* Chat Input */}
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
