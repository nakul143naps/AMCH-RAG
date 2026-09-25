import React, { useState, useEffect, useRef } from 'react'
import { Header } from './components/Header'
import { Sidebar } from './components/Sidebar'
import { ChatMessage } from './components/ChatMessage'
import { ChatInput } from './components/ChatInput'
import { CitationDrawer } from './components/CitationDrawer'
import { SystemMonitor } from './components/SystemMonitor'
import type { Message, Citation, DocumentItem, SystemHealth } from './types'
import { Sparkles, Compass, BookOpen, ShieldCheck } from 'lucide-react'

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<'chat' | 'monitor'>('chat')
  const [messages, setMessages] = useState<Message[]>([])
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [sessionId, setSessionId] = useState<string>(() => `sess_${Date.now()}`)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Auto-scroll to latest message
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    if (currentView === 'chat') {
      scrollToBottom()
    }
  }, [messages, currentView])

  // Initial Fetch: Documents, Summaries, and System Health
  const loadDocuments = async () => {
    try {
      const docRes = await fetch('/documents')
      const sumRes = await fetch('/documents/summaries')
      const docData = await docRes.json()
      const sumData = await sumRes.json()

      const summariesMap = (sumData.summaries || []).reduce(
        (acc: Record<string, any>, s: any) => {
          acc[s.doc_id] = s
          return acc
        },
        {}
      )

      const enrichedDocs: DocumentItem[] = (docData.documents || []).map((d: any) => ({
        ...d,
        topics: summariesMap[d.doc_id]?.topics || d.summary || '',
        summary: summariesMap[d.doc_id]?.summary || '',
      }))

      setDocuments(enrichedDocs)
    } catch (err) {
      console.error('Error loading documents:', err)
    }
  }

  const loadHealth = async () => {
    try {
      const res = await fetch('/health')
      if (res.ok) {
        const data = await res.json()
        setHealth(data)
      }
    } catch (err) {
      console.error('Error loading health:', err)
    }
  }

  useEffect(() => {
    loadDocuments()
    loadHealth()
    const interval = setInterval(loadHealth, 15000)
    return () => clearInterval(interval)
  }, [])

  // Document Ingestion
  const handleUploadFile = async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('access_level', 'default')

    const res = await fetch('/ingest/file', {
      method: 'POST',
      body: formData,
    })

    if (!res.ok) {
      throw new Error(`Upload failed with status ${res.status}`)
    }

    await loadDocuments()
  }

  const handleIngestUrl = async (url: string) => {
    const res = await fetch('/ingest/url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: jsonStringify({ url, access_level: 'default' }),
    })

    if (!res.ok) {
      throw new Error(`URL ingestion failed with status ${res.status}`)
    }

    await loadDocuments()
  }

  const handleDeleteDocument = async (docId: string) => {
    const res = await fetch(`/documents/${docId}`, { method: 'DELETE' })
    if (res.ok) {
      setDocuments((prev) => prev.filter((d) => d.doc_id !== docId))
    }
  }

  const handleClearCache = async () => {
    try {
      await fetch('/query/cache', { method: 'DELETE' })
    } catch (e) {
      console.error('Failed to clear cache:', e)
    }
  }

  // Streaming SSE Query Handler
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
        body: jsonStringify({
          query: queryText,
          session_id: sessionId,
          user_id: 'enterprise_user',
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
              console.warn('Malformed SSE event chunk:', err, jsonStr)
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
                    'I encountered an error retrieving or validating information from the knowledge base. Please try again or check the system status.',
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
        body: jsonStringify({ trace_id: traceId, rating }),
      })
    } catch (e) {
      console.error('Feedback dispatch error:', e)
    }
  }

  function jsonStringify(obj: any) {
    return JSON.stringify(obj)
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#090d16] font-sans text-slate-100">
      {/* Sidebar Knowledge Hub (Slide-over for User View) */}
      <Sidebar
        documents={documents}
        onUploadFile={handleUploadFile}
        onIngestUrl={handleIngestUrl}
        onDeleteDocument={handleDeleteDocument}
        onRefresh={loadDocuments}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      {/* Main Workspace Area */}
      <div className="flex-1 flex flex-col min-w-0 h-full relative">
        <Header
          currentView={currentView}
          onViewChange={(v) => setCurrentView(v)}
          onResetSession={() => {
            setSessionId(`sess_${Date.now()}`)
            setMessages([])
          }}
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
          isSidebarOpen={isSidebarOpen}
          documentCount={documents.length}
        />

        {/* VIEW 1: Regular User Chat Assistant */}
        {currentView === 'chat' && (
          <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden relative">
            {/* Messages Feed */}
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
                    Search and synthesize information across your company's indexed documents, AI engineering guides, roadmaps, and technical specifications.
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
                      <p className="text-[11px] text-slate-500 leading-normal">Explore the 9 key clusters from the AI Engineer Field Guide</p>
                    </button>

                    <button
                      onClick={() => handleSendMessage('Explain inductive vs transductive transfer learning in detail')}
                      className="p-4 rounded-xl bg-slate-900/60 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all text-left group"
                    >
                      <div className="flex items-center gap-2 text-xs font-semibold text-slate-300 group-hover:text-purple-400 mb-1">
                        <BookOpen className="w-4 h-4 text-purple-400" />
                        <span>Transfer Learning</span>
                      </div>
                      <p className="text-[11px] text-slate-500 leading-normal">Deep dive into fine-tuning, inductive, and domain adaptation</p>
                    </button>

                    <button
                      onClick={() => handleSendMessage('What is the standard starting dosage of lisinopril?')}
                      className="p-4 rounded-xl bg-slate-900/60 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all text-left group"
                    >
                      <div className="flex items-center gap-2 text-xs font-semibold text-slate-300 group-hover:text-emerald-400 mb-1">
                        <ShieldCheck className="w-4 h-4 text-emerald-400" />
                        <span>Precision Answers</span>
                      </div>
                      <p className="text-[11px] text-slate-500 leading-normal">Fact-checked clinical reference or general factual queries</p>
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

            {/* Input Controls */}
            <ChatInput
              onSendMessage={handleSendMessage}
              isLoading={isLoading}
              onStop={handleStop}
              onUploadFile={handleUploadFile}
            />
          </div>
        )}

        {/* VIEW 2: Operations & System Monitor */}
        {currentView === 'monitor' && (
          <SystemMonitor
            health={health}
            documents={documents}
            onRefresh={async () => {
              await loadDocuments()
              await loadHealth()
            }}
            onClearCache={handleClearCache}
            onDeleteDocument={handleDeleteDocument}
            onUploadFile={handleUploadFile}
            onIngestUrl={handleIngestUrl}
          />
        )}
      </div>

      {/* Slide-Over Verified Citation Drawer */}
      <CitationDrawer
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  )
}

export default App
