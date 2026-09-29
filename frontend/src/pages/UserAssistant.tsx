import React, { useState, useEffect, useRef } from 'react'
import { UserHeader } from '../components/UserHeader'
import { ChatSidebar } from '../components/ChatSidebar'
import { ChatMessage } from '../components/ChatMessage'
import { ChatInput } from '../components/ChatInput'
import { CitationDrawer } from '../components/CitationDrawer'
import { DocumentManagerModal } from '../components/DocumentManagerModal'
import type { Message, Citation, ChatSession } from '../types'
import {
  Sparkles,
  Compass,
  BookOpen,
  Heart,
  ShieldCheck,
  Cpu,
  Layers,
  Database,
  Trash2,
  RefreshCw,
  Paperclip,
} from 'lucide-react'

const STORAGE_KEY = 'amch_chat_sessions'

export const UserAssistant: React.FC = () => {
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  })

  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed: ChatSession[] = JSON.parse(saved)
        if (parsed.length > 0) return parsed[0].id
      }
    } catch {
      // fallback
    }
    return `user_sess_${Date.now()}`
  })

  const [messages, setMessages] = useState<Message[]>([])
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [documentCount, setDocumentCount] = useState<number>(0)
  const [isDocModalOpen, setIsDocModalOpen] = useState(false)
  const [statusNotice, setStatusNotice] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const fetchDocumentCount = () => {
    fetch('/documents')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && typeof data.total === 'number') {
          setDocumentCount(data.total)
        }
      })
      .catch((err) => console.warn('Could not fetch doc count:', err))
  }

  // Fetch document count on mount
  useEffect(() => {
    fetchDocumentCount()
  }, [])

  // Sync messages whenever activeSessionId changes
  useEffect(() => {
    const current = sessions.find((s) => s.id === activeSessionId)
    if (current) {
      setMessages(current.messages || [])
    } else {
      setMessages([])
    }
  }, [activeSessionId])

  // Save sessions to localStorage
  const saveSessions = (updated: ChatSession[]) => {
    setSessions(updated)
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
    } catch (e) {
      console.warn('Failed to save sessions to localStorage:', e)
    }
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // New Chat Handler
  const handleNewChat = () => {
    const newId = `user_sess_${Date.now()}`
    setActiveSessionId(newId)
    setMessages([])
  }

  // Switch Session
  const handleSelectSession = (sessionId: string) => {
    setActiveSessionId(sessionId)
  }

  // Delete Session
  const handleDeleteSession = (sessionId: string) => {
    const remaining = sessions.filter((s) => s.id !== sessionId)
    saveSessions(remaining)
    if (sessionId === activeSessionId) {
      if (remaining.length > 0) {
        setActiveSessionId(remaining[0].id)
      } else {
        handleNewChat()
      }
    }
  }

  // Clear current thread
  const handleClearCurrentThread = () => {
    setMessages([])
    const updated = sessions.map((s) =>
      s.id === activeSessionId ? { ...s, messages: [] } : s
    )
    saveSessions(updated)
  }

  // Active session title
  const activeSession = sessions.find((s) => s.id === activeSessionId)
  const activeTitle = activeSession?.title || (messages.length > 0 ? messages[0].content.slice(0, 35) + '...' : undefined)

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

    const updatedMessages = [...messages, userMsg, initialAssistantMsg]
    setMessages(updatedMessages)
    setIsLoading(true)

    // Ensure session exists in list and update title if new
    let sessionTitle = activeSession?.title
    if (!sessionTitle || sessionTitle === 'Untitled conversation') {
      sessionTitle = queryText.length > 40 ? queryText.slice(0, 40) + '...' : queryText
    }

    const sessionExists = sessions.some((s) => s.id === activeSessionId)
    let nextSessions: ChatSession[]
    if (sessionExists) {
      nextSessions = sessions.map((s) =>
        s.id === activeSessionId
          ? { ...s, title: sessionTitle!, messages: updatedMessages }
          : s
      )
    } else {
      nextSessions = [
        {
          id: activeSessionId,
          title: sessionTitle!,
          timestamp: new Date().toLocaleDateString(),
          messages: updatedMessages,
        },
        ...sessions,
      ]
    }
    saveSessions(nextSessions)

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
          session_id: activeSessionId,
          user_id: 'personal_user',
          stream: true,
          access_level: 'default',
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

      // Final message update
      const finalizedMessages = updatedMessages.map((msg) =>
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

      setMessages(finalizedMessages)

      // Persist finalized conversation in session
      const finalSessions = nextSessions.map((s) =>
        s.id === activeSessionId ? { ...s, messages: finalizedMessages } : s
      )
      saveSessions(finalSessions)
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error('Query streaming error:', err)
        const errMsg = 'Sorry, I ran into an issue finding that answer. Please try asking again!'
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? { ...msg, content: errMsg, isStreaming: false }
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

  const handleUploadFile = async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('access_level', 'default')

    try {
      setStatusNotice(`Uploading "${file.name}" to AMCH-RAG knowledge corpus...`)
      const res = await fetch('/ingest', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) throw new Error(`Upload failed with status ${res.status}`)
      const data = await res.json()
      const jobId = data.job_id

      setStatusNotice(`Indexing "${file.name}" (Extracting, chunking & vectorizing)...`)

      // Poll job status until complete
      if (jobId) {
        let attempts = 0
        const pollInterval = setInterval(async () => {
          attempts++
          try {
            const statusRes = await fetch(`/ingest/${jobId}`)
            if (statusRes.ok) {
              const statusData = await statusRes.json()
              if (statusData.status === 'completed') {
                clearInterval(pollInterval)
                setStatusNotice(`"${file.name}" successfully indexed! (${statusData.total_chunks || 1} chunks added)`)
                setTimeout(() => setStatusNotice(null), 5000)

                // Refresh doc count
                const docsRes = await fetch('/documents')
                if (docsRes.ok) {
                  const d = await docsRes.json()
                  if (typeof d.total === 'number') setDocumentCount(d.total)
                }
              } else if (statusData.status === 'failed') {
                clearInterval(pollInterval)
                setStatusNotice(`Indexing failed: ${statusData.error || 'Unknown error'}`)
                setTimeout(() => setStatusNotice(null), 6000)
              }
            }
          } catch {
            // ignore network glitch during poll
          }

          if (attempts > 30) {
            clearInterval(pollInterval)
            setStatusNotice(`"${file.name}" uploaded. Processing in background...`)
            setTimeout(() => setStatusNotice(null), 4000)
          }
        }, 1500)
      } else {
        setStatusNotice(`"${file.name}" successfully uploaded!`)
        setTimeout(() => setStatusNotice(null), 4000)
      }
    } catch (err: any) {
      console.error('File upload error:', err)
      setStatusNotice(`Upload failed: ${err.message}`)
      setTimeout(() => setStatusNotice(null), 5000)
    }
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#f8fafc] font-sans text-slate-900">
      {/* ChatGPT-style Collapsible Sidebar */}
      <ChatSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        documentCount={documentCount}
        onManageDocs={() => setIsDocModalOpen(true)}
      />

      {/* Main Conversation Container */}
      <div className="flex-1 flex flex-col min-w-0 h-full relative">
        {/* Sticky Header with Title and Live Engine Status */}
        <UserHeader
          onResetSession={handleNewChat}
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
          isSidebarOpen={isSidebarOpen}
          activeTitle={activeTitle}
          isLoading={isLoading}
          docCount={documentCount}
          onManageDocs={() => setIsDocModalOpen(true)}
        />

        {/* Upload / Ingest Notification Banner */}
        {statusNotice && (
          <div className="bg-indigo-600 text-white text-xs py-2 px-4 flex items-center justify-between shadow-xs select-none">
            <div className="flex items-center gap-2">
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              <span>{statusNotice}</span>
            </div>
            <button
              onClick={() => setStatusNotice(null)}
              className="text-white/80 hover:text-white text-xs underline cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Persistent Sub-Header / Breadcrumb when in active chat (ChatGPT style) */}
        {messages.length > 0 && (
          <div className="border-b border-slate-200/80 bg-white/70 backdrop-blur-xs px-4 md:px-8 py-2 flex items-center justify-between text-xs text-slate-500">
            <div className="flex items-center gap-2 min-w-0">
              <span className="font-semibold text-slate-800 truncate max-w-[280px] md:max-w-md">
                {activeTitle || 'Active Conversation'}
              </span>
              <span className="text-slate-300">•</span>
              <span className="text-[11px] text-slate-400">
                {messages.length} messages
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleClearCurrentThread}
                className="hover:text-rose-600 transition-colors flex items-center gap-1 cursor-pointer"
                title="Clear current conversation"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Clear</span>
              </button>
            </div>
          </div>
        )}

        {/* Chat Feed */}
        <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6">
          <div className="max-w-3xl mx-auto space-y-6">
            {/* Always Present at the Top: AMCH-RAG Personal Assistant Header */}
            <div
              className={`flex flex-col items-center justify-center text-center mx-auto transition-all ${
                messages.length === 0
                  ? 'py-10'
                  : 'py-6 border-b border-slate-200/80 mb-4'
              }`}
            >
              <div className="w-14 h-14 md:w-16 md:h-16 rounded-2xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-violet-600 flex items-center justify-center text-white mb-4 shadow-lg shadow-indigo-500/20">
                <Sparkles className="w-7 h-7 md:w-8 md:h-8" />
              </div>

              <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900 mb-1">
                AMCH-RAG
              </h1>
              <p className="text-xs md:text-sm font-semibold text-indigo-600 tracking-wide mb-2">
                Agentic Multi-Modal Corrective Hybrid RAG
              </p>
              <p className="text-xs md:text-sm text-slate-500 leading-relaxed mb-5 max-w-lg">
                Your personal knowledge assistant featuring hybrid dense + sparse retrieval, FlashRank reranking, Self-RAG groundedness verification, and sub-10ms caching.
              </p>

              {/* Engine Capabilities Tags */}
              <div className="flex flex-wrap items-center justify-center gap-2 mb-6">
                <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                  <Database className="w-3 h-3 text-indigo-600" />
                  Qdrant Vector Store
                </span>
                <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                  <Layers className="w-3 h-3 text-indigo-600" />
                  Hybrid BM25 + Dense
                </span>
                <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                  <ShieldCheck className="w-3 h-3 text-emerald-600" />
                  Self-RAG Groundedness Gate
                </span>
                <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                  <Cpu className="w-3 h-3 text-violet-600" />
                  Sub-10ms Two-Tier Cache
                </span>
              </div>

              {/* Starter Question Cards (prominently displayed before messages) */}
              {messages.length === 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full text-left">
                  {documentCount === 0 ? (
                    <>
                      <button
                        onClick={() => {
                          const fileInput = document.getElementById('chat-file-upload') as HTMLInputElement
                          if (fileInput) fileInput.click()
                        }}
                        className="p-4 rounded-2xl bg-indigo-50/70 hover:bg-indigo-100/70 border border-indigo-200/90 shadow-xs hover:border-indigo-400 hover:shadow-sm transition-all text-left group cursor-pointer"
                      >
                        <div className="flex items-center gap-2 text-xs font-semibold text-indigo-700 group-hover:text-indigo-800 mb-1">
                          <Paperclip className="w-4 h-4 text-indigo-600" />
                          <span>Upload Knowledge</span>
                        </div>
                        <p className="text-[11px] text-slate-600 leading-normal">
                          Upload your PDF, DOCX, or notes to query with hybrid RAG
                        </p>
                      </button>

                      <button
                        onClick={() => handleSendMessage('Explain how AMCH-RAG hybrid search, FlashRank, and Self-RAG work together')}
                        className="p-4 rounded-2xl bg-white hover:bg-slate-50 border border-slate-200/90 shadow-xs hover:border-indigo-300 hover:shadow-sm transition-all text-left group cursor-pointer"
                      >
                        <div className="flex items-center gap-2 text-xs font-semibold text-slate-800 group-hover:text-indigo-600 mb-1">
                          <Sparkles className="w-4 h-4 text-indigo-500" />
                          <span>System Architecture</span>
                        </div>
                        <p className="text-[11px] text-slate-500 leading-normal">
                          Deep dive into BM25 + Dense Qdrant and self-reflective gates
                        </p>
                      </button>

                      <button
                        onClick={() => handleSendMessage('What are the key technical concepts and clusters of AI Engineering?')}
                        className="p-4 rounded-2xl bg-white hover:bg-slate-50 border border-slate-200/90 shadow-xs hover:border-indigo-300 hover:shadow-sm transition-all text-left group cursor-pointer"
                      >
                        <div className="flex items-center gap-2 text-xs font-semibold text-slate-800 group-hover:text-indigo-600 mb-1">
                          <Compass className="w-4 h-4 text-indigo-500" />
                          <span>AI Engineering</span>
                        </div>
                        <p className="text-[11px] text-slate-500 leading-normal">
                          Ask general AI, LLM router, or agentic workflow questions
                        </p>
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => handleSendMessage('Summarize the 9 AI Engineer clusters in the roadmap')}
                        className="p-4 rounded-2xl bg-white hover:bg-slate-50 border border-slate-200/90 shadow-xs hover:border-indigo-300 hover:shadow-sm transition-all text-left group cursor-pointer"
                      >
                        <div className="flex items-center gap-2 text-xs font-semibold text-slate-800 group-hover:text-indigo-600 mb-1">
                          <Compass className="w-4 h-4 text-indigo-500" />
                          <span>Study Roadmap</span>
                        </div>
                        <p className="text-[11px] text-slate-500 leading-normal">
                          Explore the 9 key clusters from the AI Engineer guide
                        </p>
                      </button>

                      <button
                        onClick={() => handleSendMessage('Explain inductive vs transductive transfer learning in detail')}
                        className="p-4 rounded-2xl bg-white hover:bg-slate-50 border border-slate-200/90 shadow-xs hover:border-indigo-300 hover:shadow-sm transition-all text-left group cursor-pointer"
                      >
                        <div className="flex items-center gap-2 text-xs font-semibold text-slate-800 group-hover:text-indigo-600 mb-1">
                          <BookOpen className="w-4 h-4 text-indigo-500" />
                          <span>Transfer Learning</span>
                        </div>
                        <p className="text-[11px] text-slate-500 leading-normal">
                          Deep dive into fine-tuning, inductive, and adaptation
                        </p>
                      </button>

                      <button
                        onClick={() => handleSendMessage('What is the standard starting dosage of lisinopril?')}
                        className="p-4 rounded-2xl bg-white hover:bg-slate-50 border border-slate-200/90 shadow-xs hover:border-indigo-300 hover:shadow-sm transition-all text-left group cursor-pointer"
                      >
                        <div className="flex items-center gap-2 text-xs font-semibold text-slate-800 group-hover:text-indigo-600 mb-1">
                          <Heart className="w-4 h-4 text-indigo-500" />
                          <span>Quick Facts</span>
                        </div>
                        <p className="text-[11px] text-slate-500 leading-normal">
                          Ask quick fact-checked questions or clinical references
                        </p>
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Conversation Messages */}
            {messages.length > 0 && (
              <div className="space-y-4">
                {messages.map((msg, idx) => {
                  const isLastAssistantMessage =
                    msg.role === 'assistant' &&
                    idx === messages.map((m) => m.role).lastIndexOf('assistant')

                  return (
                    <ChatMessage
                      key={msg.id}
                      message={msg}
                      onSelectCitation={(cit) => setSelectedCitation(cit)}
                      onFeedback={handleFeedback}
                      onFollowUp={handleSendMessage}
                      isLast={isLastAssistantMessage}
                    />
                  )
                })}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Chat Input */}
        <ChatInput
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          onStop={handleStop}
          onUploadFile={handleUploadFile}
          documentCount={documentCount}
        />
      </div>

      {/* Slide-Over Verified Citation Drawer */}
      <CitationDrawer
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />

      {/* Document Management Modal (View & Remove Knowledge Files) */}
      <DocumentManagerModal
        isOpen={isDocModalOpen}
        onClose={() => setIsDocModalOpen(false)}
        onDocumentsChanged={fetchDocumentCount}
      />
    </div>
  )
}
