import React, { useState, useEffect, useRef } from 'react'
import { Header } from './components/Header'
import { Sidebar } from './components/Sidebar'
import { ChatMessage } from './components/ChatMessage'
import { ChatInput } from './components/ChatInput'
import { CitationDrawer } from './components/CitationDrawer'
import type { Message, Citation, DocumentItem, SystemHealth } from './types'
import { Sparkles, ShieldCheck, Zap, Database } from 'lucide-react'

export const App: React.FC = () => {
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
    scrollToBottom()
  }, [messages])

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
      const data = await res.json()
      setHealth(data)
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

  // File Upload Ingestion
  const handleUploadFile = async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('access_level', 'default')

    const res = await fetch('/ingest/file', {
      method: 'POST',
      body: formData,
    })

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Upload failed')
    }

    // Refresh document list after ingestion
    setTimeout(loadDocuments, 1500)
  }

  // URL Ingestion
  const handleIngestUrl = async (url: string) => {
    const res = await fetch('/ingest/url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: jsonStringify({ url, access_level: 'default' }),
    })

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'URL ingest failed')
    }

    setTimeout(loadDocuments, 2000)
  }

  // Delete Document
  const handleDeleteDocument = async (docId: string) => {
    const res = await fetch(`/documents/${docId}`, { method: 'DELETE' })
    if (res.ok) {
      setDocuments((prev) => prev.filter((d) => d.doc_id !== docId))
    }
  }

  // Clear Cache
  const handleClearCache = async () => {
    await fetch('/documents/cache/clear', { method: 'POST' })
  }

  // Send Query via SSE Streaming
  const handleSendMessage = async (queryText: string) => {
    const userMsgId = `usr_${Date.now()}`
    const assistantMsgId = `ast_${Date.now()}`
    const startTime = performance.now()

    // Append User Message
    const userMsg: Message = {
      id: userMsgId,
      role: 'user',
      content: queryText,
      timestamp: new Date().toLocaleTimeString(),
    }

    // Initial empty streaming assistant message
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
      let providerUsed = 'groq'

      if (reader) {
        let buffer = ''
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            const trimmed = line.trim()
            if (trimmed.startsWith('data: ')) {
              try {
                const event = JSON.parse(trimmed.slice(6))
                if (event.type === 'token') {
                  fullContent += event.content
                } else if (event.type === 'citation') {
                  collectedCitations.push(event)
                } else if (event.type === 'correction') {
                  collectedCorrections.push(event.reason)
                } else if (event.type === 'done') {
                  traceId = event.trace_id || ''
                }
              } catch (e) {
                // partial json or text
              }
            }
          }

          // Update streaming state live
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    content: fullContent,
                    citations: [...collectedCitations],
                    corrections: [...collectedCorrections],
                    trace_id: traceId,
                    provider_used: providerUsed,
                    latency: (performance.now() - startTime) / 1000,
                  }
                : m
            )
          )
        }
      }

      // Final state once done
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? {
                ...m,
                isStreaming: false,
                content: fullContent || m.content,
                citations: collectedCitations,
                corrections: collectedCorrections,
                trace_id: traceId,
                latency: (performance.now() - startTime) / 1000,
              }
            : m
        )
      )
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  isStreaming: false,
                  content: `⚠️ Query execution failed: ${err.message || 'Error communicating with backend'}.`,
                }
              : m
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
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 font-sans text-slate-100">
      {/* Sidebar Knowledge Hub */}
      <Sidebar
        documents={documents}
        onUploadFile={handleUploadFile}
        onIngestUrl={handleIngestUrl}
        onDeleteDocument={handleDeleteDocument}
        onClearCache={handleClearCache}
        onRefresh={loadDocuments}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 h-full relative">
        <Header
          health={health}
          sessionId={sessionId}
          onResetSession={() => {
            setSessionId(`sess_${Date.now()}`)
            setMessages([])
          }}
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
          isSidebarOpen={isSidebarOpen}
        />

        {/* Messages Feed */}
        <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-xl mx-auto py-12">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-xl shadow-blue-500/20 mb-6">
                <Sparkles className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold tracking-tight text-white mb-2">
                Enterprise AMCH-RAG Assistant
              </h2>
              <p className="text-sm text-slate-400 leading-relaxed mb-8">
                Ask questions about your uploaded documents, roadmaps, systems, or general concepts.
                Every response is validated through Self-RAG groundedness checks and two-tier caching.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full text-left">
                <div className="p-4 rounded-xl glass-panel border border-slate-800">
                  <div className="flex items-center gap-2 text-xs font-semibold text-blue-400 mb-1">
                    <Database className="w-4 h-4" />
                    <span>Qdrant Hybrid</span>
                  </div>
                  <p className="text-xs text-slate-400">Dense vectors & BM25 fused with FlashRank</p>
                </div>

                <div className="p-4 rounded-xl glass-panel border border-slate-800">
                  <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400 mb-1">
                    <ShieldCheck className="w-4 h-4" />
                    <span>Self-RAG CRAG</span>
                  </div>
                  <p className="text-xs text-slate-400">Zero hallucinations with automatic groundedness checks</p>
                </div>

                <div className="p-4 rounded-xl glass-panel border border-slate-800">
                  <div className="flex items-center gap-2 text-xs font-semibold text-amber-400 mb-1">
                    <Zap className="w-4 h-4" />
                    <span>Sub-10ms Cache</span>
                  </div>
                  <p className="text-xs text-slate-400">Instant answers for repeated questions & chit-chat</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto space-y-4">
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

export default App
