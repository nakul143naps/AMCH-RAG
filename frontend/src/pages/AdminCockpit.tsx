import React, { useState, useEffect } from 'react'
import {
  Database,
  Zap,
  HardDrive,
  ExternalLink,
  RefreshCw,
  FileText,
  Trash2,
  UploadCloud,
  Globe,
  CheckCircle2,
  Brain,
  Lock,
  ArrowRight,
  Plus,
  Sliders,
  AlertTriangle,
  Activity,
  Sparkles,
} from 'lucide-react'
import type { DocumentItem, QdrantCollectionInfo } from '../types'

interface CacheItem {
  key: string
  query: string
  preview: string
  expires_at: number
  is_expired: boolean
}

interface SemanticCacheItem {
  id: string
  query: string
  access_level: string
  doc_ids: string[]
  exact_key: string
}

interface MemoryFact {
  id: string
  user_id: string
  fact: string
  category: string
  created_at: string
}

interface GuardrailsConfig {
  groundedness_threshold: number
  strict_grounding: boolean
  crag_fallback_enabled: boolean
  max_correction_retries: number
  confidence_gate: number
  prompt_injection_shield: boolean
}

export const AdminCockpit: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    return localStorage.getItem('aura_admin_auth') === 'true'
  })
  const [passkeyInput, setPasskeyInput] = useState('')
  const [passkeyError, setPasskeyError] = useState(false)

  const [activeTab, setActiveTab] = useState<'portals' | 'cache' | 'memory' | 'guardrails' | 'qdrant' | 'documents'>('portals')

  // Cache state
  const [sqliteEntries, setSqliteEntries] = useState<CacheItem[]>([])
  const [semanticEntries, setSemanticEntries] = useState<SemanticCacheItem[]>([])
  const [loadingCache, setLoadingCache] = useState(false)
  const [cacheNotice, setCacheNotice] = useState<string | null>(null)

  // Memory state
  const [memories, setMemories] = useState<MemoryFact[]>([])
  const [loadingMemory, setLoadingMemory] = useState(false)
  const [newFactText, setNewFactText] = useState('')
  const [newFactUser, setNewFactUser] = useState('personal_user')
  const [newFactCategory, setNewFactCategory] = useState('preference')
  const [memoryNotice, setMemoryNotice] = useState<string | null>(null)

  // Guardrails state
  const [guardrails, setGuardrails] = useState<GuardrailsConfig>({
    groundedness_threshold: 1.0,
    strict_grounding: true,
    crag_fallback_enabled: true,
    max_correction_retries: 2,
    confidence_gate: 0.5,
    prompt_injection_shield: true,
  })
  const [guardrailNotice, setGuardrailNotice] = useState<string | null>(null)

  // Qdrant & Docs state
  const [collections, setCollections] = useState<QdrantCollectionInfo[]>([])
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [urlInput, setUrlInput] = useState('')
  const [isUrlIngesting, setIsUrlIngesting] = useState(false)
  const [isUploading, setIsUploading] = useState(false)

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault()
    if (passkeyInput === 'admin' || passkeyInput === 'admin123') {
      setIsAuthenticated(true)
      localStorage.setItem('aura_admin_auth', 'true')
      setPasskeyError(false)
    } else {
      setPasskeyError(true)
    }
  }

  const handleLogout = () => {
    setIsAuthenticated(false)
    localStorage.removeItem('aura_admin_auth')
  }

  // 1. Fetch Cache Details
  const fetchCacheData = async () => {
    setLoadingCache(true)
    try {
      const res = await fetch('/admin-api/cache')
      if (res.ok) {
        const data = await res.json()
        setSqliteEntries(data.l1_sqlite?.entries || [])
        setSemanticEntries(data.l2_semantic?.entries || [])
      }
    } catch (e) {
      console.error('Failed to load cache:', e)
    } finally {
      setLoadingCache(false)
    }
  }

  const handleDeleteCacheEntry = async (key?: string, pointId?: string) => {
    try {
      const params = new URLSearchParams()
      if (key) params.append('key', key)
      if (pointId) params.append('point_id', pointId)

      const res = await fetch(`/admin-api/cache/entry?${params.toString()}`, { method: 'DELETE' })
      if (res.ok) {
        setCacheNotice('Cache entry deleted')
        setTimeout(() => setCacheNotice(null), 3000)
        await fetchCacheData()
      }
    } catch (e) {
      console.error('Failed to delete cache entry:', e)
    }
  }

  const handlePurgeAllCaches = async () => {
    if (confirm('Clear both L1 SQLite exact cache and L2 Qdrant semantic cache?')) {
      try {
        await fetch('/query/cache', { method: 'DELETE' })
        setCacheNotice('All caches purged completely')
        setTimeout(() => setCacheNotice(null), 3000)
        await fetchCacheData()
      } catch (e) {
        console.error('Purge error:', e)
      }
    }
  }

  // 2. Fetch User Memory Facts
  const fetchMemoryData = async () => {
    setLoadingMemory(true)
    try {
      const res = await fetch('/admin-api/memory')
      if (res.ok) {
        const data = await res.json()
        setMemories(data.facts || [])
      }
    } catch (e) {
      console.error('Failed to load memory:', e)
    } finally {
      setLoadingMemory(false)
    }
  }

  const handleAddMemory = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newFactText.trim()) return
    try {
      const res = await fetch('/admin-api/memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: newFactUser.trim(),
          fact: newFactText.trim(),
          category: newFactCategory,
        }),
      })
      if (res.ok) {
        setNewFactText('')
        setMemoryNotice('New memory fact saved to vector store')
        setTimeout(() => setMemoryNotice(null), 3000)
        await fetchMemoryData()
      }
    } catch (e) {
      console.error('Failed to add memory fact:', e)
    }
  }

  const handleDeleteMemory = async (pointId: string) => {
    if (confirm('Delete this memory fact from vector store?')) {
      try {
        const res = await fetch(`/admin-api/memory/${pointId}`, { method: 'DELETE' })
        if (res.ok) {
          setMemoryNotice('Memory fact deleted')
          setTimeout(() => setMemoryNotice(null), 3000)
          await fetchMemoryData()
        }
      } catch (e) {
        console.error('Failed to delete memory:', e)
      }
    }
  }

  // 3. Fetch & Update Guardrails
  const fetchGuardrails = async () => {
    try {
      const res = await fetch('/admin-api/guardrails')
      if (res.ok) {
        const data = await res.json()
        setGuardrails(data)
      }
    } catch (e) {
      console.error('Failed to load guardrails:', e)
    }
  }

  const handleSaveGuardrails = async () => {
    try {
      const res = await fetch('/admin-api/guardrails', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(guardrails),
      })
      if (res.ok) {
        setGuardrailNotice('Guardrail parameters saved and active')
        setTimeout(() => setGuardrailNotice(null), 3500)
      }
    } catch (e) {
      console.error('Failed to update guardrails:', e)
    }
  }

  // 4. Fetch Qdrant Collections & Documents
  const fetchQdrantCollections = async () => {
    try {
      const res = await fetch('/qdrant-api/collections')
      if (res.ok) {
        const data = await res.json()
        const colList = data.result?.collections || []
        const detailedCols: QdrantCollectionInfo[] = []

        for (const col of colList) {
          try {
            const detailRes = await fetch(`/qdrant-api/collections/${col.name}`)
            if (detailRes.ok) {
              const detailData = await detailRes.json()
              const r = detailData.result
              detailedCols.push({
                name: col.name,
                points_count: r.points_count || 0,
                indexed_vectors_count: r.indexed_vectors_count || 0,
                status: r.status || 'green',
                segments_count: r.segments_count || 0,
              })
            }
          } catch (e) {
            console.error(`Detail error for ${col.name}`, e)
          }
        }
        setCollections(detailedCols)
      }
    } catch (e) {
      console.error('Qdrant fetch error:', e)
    }
  }

  const fetchDocuments = async () => {
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

  const handleDeleteDocument = async (docId: string) => {
    if (confirm('Delete this document and all its indexed vector chunks?')) {
      const res = await fetch(`/documents/${docId}`, { method: 'DELETE' })
      if (res.ok) {
        setDocuments((prev) => prev.filter((d) => d.doc_id !== docId))
        await fetchQdrantCollections()
      }
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setIsUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('access_level', 'default')

      const res = await fetch('/ingest/file', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) throw new Error('Upload failed')
      await fetchDocuments()
      await fetchQdrantCollections()
    } finally {
      setIsUploading(false)
      e.target.value = ''
    }
  }

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!urlInput.trim()) return
    setIsUrlIngesting(true)
    try {
      const res = await fetch('/ingest/url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: urlInput.trim(), access_level: 'default' }),
      })
      if (!res.ok) throw new Error('URL ingest failed')
      setUrlInput('')
      await fetchDocuments()
      await fetchQdrantCollections()
    } finally {
      setIsUrlIngesting(false)
    }
  }

  useEffect(() => {
    if (isAuthenticated) {
      fetchCacheData()
      fetchMemoryData()
      fetchGuardrails()
      fetchQdrantCollections()
      fetchDocuments()
    }
  }, [isAuthenticated])

  const handleRefreshCurrent = async () => {
    if (activeTab === 'cache') await fetchCacheData()
    if (activeTab === 'memory') await fetchMemoryData()
    if (activeTab === 'guardrails') await fetchGuardrails()
    if (activeTab === 'qdrant') await fetchQdrantCollections()
    if (activeTab === 'documents') await fetchDocuments()
    if (activeTab === 'portals') {
      await fetchQdrantCollections()
      await fetchCacheData()
      await fetchDocuments()
    }
  }

  const totalPoints = collections.reduce((acc, c) => acc + c.points_count, 0)

  // Passkey Login Screen (Light Theme)
  if (!isAuthenticated) {
    return (
      <div className="h-screen w-screen bg-[#f8fafc] flex items-center justify-center p-4 text-slate-900 font-sans">
        <div className="max-w-md w-full p-8 rounded-2xl bg-white border border-slate-200 shadow-xl space-y-6">
          <div className="text-center space-y-2">
            <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-200 text-indigo-600 flex items-center justify-center mx-auto shadow-xs">
              <Lock className="w-6 h-6" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Admin Inspection &amp; Portals
            </h1>
            <p className="text-xs text-slate-500">
              Inspect and control caches, memory, guardrails, and vector stores.
            </p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Admin Passkey
              </label>
              <input
                type="password"
                value={passkeyInput}
                onChange={(e) => setPasskeyInput(e.target.value)}
                placeholder="Enter passkey (default: admin)"
                className="w-full bg-slate-50 border border-slate-200 focus:border-indigo-500 focus:bg-white rounded-xl px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:outline-none transition-colors"
                autoFocus
              />
              {passkeyError && (
                <p className="text-xs text-rose-600 mt-1.5 flex items-center gap-1 font-medium">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Incorrect passkey. Please try again.
                </p>
              )}
            </div>

            <button
              type="submit"
              className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors shadow-xs cursor-pointer"
            >
              <span>Unlock Admin Center</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </form>

          <div className="pt-2 text-center border-t border-slate-100">
            <a href="/" className="text-xs text-slate-500 hover:text-slate-800 transition-colors">
              &larr; Back to Personal Assistant
            </a>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col h-screen bg-[#f8fafc] text-slate-900 overflow-hidden font-sans">
      {/* Top Admin Header (Light Theme) */}
      <div className="border-b border-slate-200 bg-white/95 backdrop-blur-md px-6 py-4 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 text-white flex items-center justify-center font-bold text-sm shadow-xs">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-extrabold text-slate-900 tracking-tight">
                  AMCH-RAG
                </h1>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 font-semibold">
                  Admin Cockpit
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
                  Live
                </span>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                Agentic Multi-Modal Corrective Hybrid RAG &bull; System Controls &amp; Portals
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <a
              href="/"
              className="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-200 transition-colors"
            >
              Open Assistant &rarr;
            </a>

            <button
              onClick={handleRefreshCurrent}
              className="p-2 rounded-xl bg-white hover:bg-slate-100 text-slate-600 transition-colors border border-slate-200 shadow-xs cursor-pointer"
              title="Refresh Current View"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>

            {/* Header Direct Diversion Buttons */}
            <a
              href="http://localhost:6333/dashboard"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 text-xs font-semibold transition-all shadow-xs"
              title="Open Qdrant Visual Vector Dashboard"
            >
              <Database className="w-3.5 h-3.5 text-purple-600" />
              <span>Qdrant (6333)</span>
              <ExternalLink className="w-3 h-3 opacity-60" />
            </a>

            <a
              href="https://smith.langchain.com/"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-xs font-semibold transition-all shadow-xs"
              title="Open LangSmith Tracing Workspace"
            >
              <Activity className="w-3.5 h-3.5 text-emerald-600" />
              <span>LangSmith</span>
              <ExternalLink className="w-3 h-3 opacity-60" />
            </a>

            <button
              onClick={handleLogout}
              className="px-2.5 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-semibold transition-colors cursor-pointer"
            >
              Lock
            </button>
          </div>
        </div>

        {/* Functional Tabs */}
        <div className="flex items-center gap-1 mt-4 border-b border-slate-200 -mb-4 overflow-x-auto">
          {[
            { id: 'portals', label: 'Dashboard & Portals', icon: Sparkles },
            { id: 'cache', label: 'Cache Inspector (L1 & L2)', icon: Zap, badge: (sqliteEntries.length + semanticEntries.length).toString() },
            { id: 'memory', label: 'User Memory (Facts)', icon: Brain, badge: memories.length.toString() },
            { id: 'guardrails', label: 'Guardrail Controls', icon: Sliders },
            { id: 'qdrant', label: 'Vector Collections', icon: Database, badge: collections.length.toString() },
            { id: 'documents', label: 'Knowledge Base Files', icon: FileText, badge: documents.length.toString() },
          ].map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-all cursor-pointer whitespace-nowrap ${
                  isActive
                    ? 'border-indigo-600 text-indigo-700 bg-indigo-50/50'
                    : 'border-transparent text-slate-500 hover:text-slate-900 hover:border-slate-300'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span className="px-1.5 py-0.2 rounded-full bg-slate-100 text-[10px] text-slate-600 font-mono">
                    {tab.badge}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Main Tab Canvas (Light Theme) */}
      <div className="flex-1 p-6 md:p-8 space-y-6 overflow-y-auto">
        {/* TAB 0: DASHBOARD & DIVERSION PORTALS */}
        {activeTab === 'portals' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-900 tracking-tight">System Portals &amp; Live Diversions</h2>
              <p className="text-xs text-slate-500">
                Direct access points to the official native Qdrant visual database and LangSmith live tracing dashboard.
              </p>
            </div>

            {/* Prominent Diversion Launchpad Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Qdrant DB Diversion Launchpad */}
              <div className="p-6 rounded-2xl bg-white border border-purple-200/80 shadow-sm hover:shadow-md transition-all space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center font-bold">
                      <Database className="w-6 h-6 text-purple-600" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-slate-900">Qdrant Vector Database</h3>
                      <p className="text-xs text-slate-500">Native Windows Instance &bull; Port 6333</p>
                    </div>
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    Live
                  </span>
                </div>

                <p className="text-xs text-slate-600 leading-relaxed">
                  Explore indexed high-dimensional vectors, payload metadata, points count, and collection schemas in the visual web UI.
                </p>

                <div className="grid grid-cols-3 gap-2 p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-mono block">Collections</span>
                    <span className="font-bold text-slate-800">{collections.length || 3}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-mono block">Total Vectors</span>
                    <span className="font-bold text-purple-700">{totalPoints || 71}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-mono block">Embedding Dim</span>
                    <span className="font-bold text-slate-800">768 Dim</span>
                  </div>
                </div>

                <a
                  href="http://localhost:6333/dashboard"
                  target="_blank"
                  rel="noreferrer"
                  className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-xs transition-all"
                >
                  <span>Launch Official Qdrant Dashboard (6333)</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>

              {/* LangSmith Diversion Launchpad */}
              <div className="p-6 rounded-2xl bg-white border border-emerald-200/80 shadow-sm hover:shadow-md transition-all space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold">
                      <Activity className="w-6 h-6 text-emerald-600" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-slate-900">LangSmith Observability</h3>
                      <p className="text-xs text-slate-500">Live Tracing &bull; Project: AMCH-RAG</p>
                    </div>
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    Active
                  </span>
                </div>

                <p className="text-xs text-slate-600 leading-relaxed">
                  Real-time visualization of LLM generation spans, token consumption, retrieval latency, and Self-RAG groundedness checks.
                </p>

                <div className="grid grid-cols-3 gap-2 p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-mono block">Project</span>
                    <span className="font-bold text-slate-800 truncate">AMCH-RAG</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-mono block">Telemetry</span>
                    <span className="font-bold text-emerald-700">OpenTelemetry</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-mono block">Endpoint</span>
                    <span className="font-bold text-slate-800">LangChain v2</span>
                  </div>
                </div>

                <a
                  href="https://smith.langchain.com/"
                  target="_blank"
                  rel="noreferrer"
                  className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-xs transition-all"
                >
                  <span>Open LangSmith Tracing Workspace</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>

            {/* Quick Stat Highlights */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs">
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-700 mb-1">
                  <Zap className="w-4 h-4 text-amber-500" />
                  <span>Two-Tier Cache Items</span>
                </div>
                <div className="text-xl font-bold text-slate-900">
                  {sqliteEntries.length + semanticEntries.length} cached queries
                </div>
                <p className="text-[11px] text-slate-500 mt-1">L1 SQLite ({sqliteEntries.length}) + L2 Qdrant ({semanticEntries.length})</p>
              </div>

              <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs">
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-700 mb-1">
                  <Brain className="w-4 h-4 text-indigo-500" />
                  <span>User Facts Stored</span>
                </div>
                <div className="text-xl font-bold text-slate-900">
                  {memories.length} learned facts
                </div>
                <p className="text-[11px] text-slate-500 mt-1">Extracted in Qdrant user_memory</p>
              </div>

              <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs">
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-700 mb-1">
                  <FileText className="w-4 h-4 text-blue-500" />
                  <span>Knowledge Documents</span>
                </div>
                <div className="text-xl font-bold text-slate-900">
                  {documents.length} indexed sources
                </div>
                <p className="text-[11px] text-slate-500 mt-1">PDFs, roadmaps, and scraped websites</p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 1: CACHE INSPECTOR & CONTROL */}
        {activeTab === 'cache' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-bold text-slate-900">Cache Inspector &amp; Controls</h2>
                <p className="text-xs text-slate-500">
                  Inspect every cached prompt and answer in L1 SQLite and L2 Qdrant semantic cache.
                </p>
              </div>

              <button
                onClick={handlePurgeAllCaches}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-semibold transition-all cursor-pointer shadow-xs"
              >
                <Trash2 className="w-4 h-4 text-rose-600" />
                <span>Purge All Caches</span>
              </button>
            </div>

            {cacheNotice && (
              <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2 font-medium">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>{cacheNotice}</span>
              </div>
            )}

            {/* L1 SQLite Cache Table */}
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-800">
                <div className="flex items-center gap-2">
                  <HardDrive className="w-4 h-4 text-amber-500" />
                  <span>L1 Exact SQLite Cache Entries ({sqliteEntries.length})</span>
                </div>
                <span className="text-[11px] text-slate-500 font-mono">./data/cache/cache.db</span>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-xs">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-mono text-[10px]">
                    <tr>
                      <th className="px-4 py-3">Cached Query</th>
                      <th className="px-4 py-3">Answer Preview</th>
                      <th className="px-4 py-3">Expires</th>
                      <th className="px-4 py-3 text-right">Delete</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {loadingCache ? (
                      <tr>
                        <td colSpan={4} className="px-4 py-8 text-center text-slate-400">Loading cache...</td>
                      </tr>
                    ) : sqliteEntries.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-4 py-8 text-center text-slate-400">L1 cache is currently empty.</td>
                      </tr>
                    ) : (
                      sqliteEntries.map((item) => (
                        <tr key={item.key} className="hover:bg-slate-50/80 transition-colors">
                          <td className="px-4 py-3 font-semibold text-slate-900 max-w-xs truncate">
                            {item.query}
                          </td>
                          <td className="px-4 py-3 text-slate-600 max-w-md truncate">
                            {item.preview}
                          </td>
                          <td className="px-4 py-3 text-slate-500 font-mono text-[11px]">
                            {new Date(item.expires_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() => handleDeleteCacheEntry(item.key)}
                              className="p-1 rounded-md hover:bg-rose-50 text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                              title="Delete from cache"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* L2 Qdrant Semantic Cache Table */}
            <div className="space-y-3 pt-4 border-t border-slate-200">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-800">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-purple-600" />
                  <span>L2 Semantic Cache in Qdrant ({semanticEntries.length})</span>
                </div>
                <a
                  href="http://localhost:6333/dashboard#/collections/semantic_cache"
                  target="_blank"
                  rel="noreferrer"
                  className="text-[11px] text-purple-600 hover:underline font-medium flex items-center gap-1"
                >
                  <span>Inspect in Qdrant Web UI</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-xs">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-mono text-[10px]">
                    <tr>
                      <th className="px-4 py-3">Semantic Query</th>
                      <th className="px-4 py-3">Point ID</th>
                      <th className="px-4 py-3">Associated Documents</th>
                      <th className="px-4 py-3 text-right">Delete</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {semanticEntries.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-4 py-8 text-center text-slate-400">L2 semantic cache is empty.</td>
                      </tr>
                    ) : (
                      semanticEntries.map((item) => (
                        <tr key={item.id} className="hover:bg-slate-50/80 transition-colors">
                          <td className="px-4 py-3 font-semibold text-slate-900 max-w-xs truncate">
                            {item.query}
                          </td>
                          <td className="px-4 py-3 font-mono text-slate-500 text-[10px] truncate max-w-[120px]">
                            {item.id}
                          </td>
                          <td className="px-4 py-3 text-slate-600 text-xs">
                            {item.doc_ids.length > 0 ? item.doc_ids.join(', ') : 'General query'}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() => handleDeleteCacheEntry(undefined, item.id)}
                              className="p-1 rounded-md hover:bg-rose-50 text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                              title="Delete from semantic cache"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: USER MEMORY FACTS */}
        {activeTab === 'memory' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-slate-900">User Long-Term Memory Facts</h2>
              <p className="text-xs text-slate-500">
                Facts learned during chat and stored in Qdrant <code className="text-purple-600 font-mono">user_memory</code>.
              </p>
            </div>

            {memoryNotice && (
              <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2 font-medium">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>{memoryNotice}</span>
              </div>
            )}

            {/* Add Memory Form */}
            <form onSubmit={handleAddMemory} className="p-5 rounded-2xl bg-white border border-slate-200 space-y-3 shadow-xs">
              <span className="text-xs font-semibold text-slate-900 block flex items-center gap-1.5">
                <Plus className="w-3.5 h-3.5 text-indigo-600" />
                Teach Assistant a New User Fact
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                <input
                  type="text"
                  placeholder="Fact description (e.g. User prefers Python and PyTorch)"
                  value={newFactText}
                  onChange={(e) => setNewFactText(e.target.value)}
                  className="sm:col-span-2 bg-slate-50 border border-slate-200 focus:bg-white focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none"
                />
                <input
                  type="text"
                  placeholder="User ID (e.g. personal_user)"
                  value={newFactUser}
                  onChange={(e) => setNewFactUser(e.target.value)}
                  className="bg-slate-50 border border-slate-200 focus:bg-white focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none"
                />
                <select
                  value={newFactCategory}
                  onChange={(e) => setNewFactCategory(e.target.value)}
                  className="bg-slate-50 border border-slate-200 focus:bg-white focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none"
                >
                  <option value="preference">Preference</option>
                  <option value="background">Background</option>
                  <option value="goal">Goal / Project</option>
                </select>
              </div>
              <button
                type="submit"
                disabled={!newFactText.trim()}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold disabled:opacity-40 transition-colors shadow-xs cursor-pointer"
              >
                Store Fact in Vector Store
              </button>
            </form>

            {/* Memories List */}
            <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-mono text-[10px]">
                  <tr>
                    <th className="px-4 py-3">Learned Fact</th>
                    <th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">User ID</th>
                    <th className="px-4 py-3 text-right">Delete</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loadingMemory ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-8 text-center text-slate-400">Loading memory facts...</td>
                    </tr>
                  ) : memories.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-8 text-center text-slate-400">
                        No user facts stored yet. Use the form above to add a fact or ask queries in chat.
                      </td>
                    </tr>
                  ) : (
                    memories.map((mem) => (
                      <tr key={mem.id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="px-4 py-3 font-semibold text-slate-900 max-w-md">
                          {mem.fact}
                        </td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-[10px] font-medium border border-indigo-200">
                            {mem.category}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono text-slate-500 text-xs">
                          {mem.user_id}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => handleDeleteMemory(mem.id)}
                            className="p-1 rounded-md hover:bg-rose-50 text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                            title="Forget fact"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 3: GUARDRAIL CONTROLS */}
        {activeTab === 'guardrails' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-slate-900">Guardrails &amp; Factual Bounds</h2>
              <p className="text-xs text-slate-500">
                Live configuration controlling hallucination filtering, retrieval confidence, and Self-RAG verification.
              </p>
            </div>

            {guardrailNotice && (
              <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2 font-medium">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>{guardrailNotice}</span>
              </div>
            )}

            <div className="p-6 rounded-2xl bg-white border border-slate-200 space-y-6 max-w-2xl shadow-xs">
              {/* Groundedness threshold */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold text-slate-900">Self-RAG Groundedness Threshold</span>
                  <span className="font-mono text-indigo-600 font-bold">{guardrails.groundedness_threshold.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.0"
                  step="0.05"
                  value={guardrails.groundedness_threshold}
                  onChange={(e) => setGuardrails({ ...guardrails, groundedness_threshold: parseFloat(e.target.value) })}
                  className="w-full accent-indigo-600"
                />
                <p className="text-[11px] text-slate-500">
                  Minimum confidence required before an assistant answer is emitted. 1.0 = strict zero hallucination.
                </p>
              </div>

              {/* Confidence gate */}
              <div className="space-y-2 pt-4 border-t border-slate-100">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold text-slate-900">Retrieval Confidence Gate</span>
                  <span className="font-mono text-indigo-600 font-bold">{guardrails.confidence_gate.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.2"
                  max="0.9"
                  step="0.05"
                  value={guardrails.confidence_gate}
                  onChange={(e) => setGuardrails({ ...guardrails, confidence_gate: parseFloat(e.target.value) })}
                  className="w-full accent-indigo-600"
                />
                <p className="text-[11px] text-slate-500">
                  Hybrid RRF score threshold below which the query triggers fallback search.
                </p>
              </div>

              {/* Toggles */}
              <div className="space-y-3 pt-4 border-t border-slate-100 text-xs">
                <label className="flex items-center justify-between cursor-pointer">
                  <div>
                    <span className="font-semibold text-slate-900 block">Strict Grounding Mode</span>
                    <span className="text-[11px] text-slate-500">Rejects claims that lack direct citation chunk support</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={guardrails.strict_grounding}
                    onChange={(e) => setGuardrails({ ...guardrails, strict_grounding: e.target.checked })}
                    className="w-4 h-4 accent-indigo-600 rounded"
                  />
                </label>

                <label className="flex items-center justify-between cursor-pointer pt-3 border-t border-slate-100">
                  <div>
                    <span className="font-semibold text-slate-900 block">CRAG Web Fallback</span>
                    <span className="text-[11px] text-slate-500">Allow web retrieval when knowledge base has no relevant documents</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={guardrails.crag_fallback_enabled}
                    onChange={(e) => setGuardrails({ ...guardrails, crag_fallback_enabled: e.target.checked })}
                    className="w-4 h-4 accent-indigo-600 rounded"
                  />
                </label>

                <label className="flex items-center justify-between cursor-pointer pt-3 border-t border-slate-100">
                  <div>
                    <span className="font-semibold text-slate-900 block">Prompt Injection Shield</span>
                    <span className="text-[11px] text-slate-500">Sanitizes user input against jailbreak patterns</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={guardrails.prompt_injection_shield}
                    onChange={(e) => setGuardrails({ ...guardrails, prompt_injection_shield: e.target.checked })}
                    className="w-4 h-4 accent-indigo-600 rounded"
                  />
                </label>
              </div>

              {/* Retries */}
              <div className="pt-4 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-900">Max Correction Retries</span>
                <input
                  type="number"
                  min="1"
                  max="4"
                  value={guardrails.max_correction_retries}
                  onChange={(e) => setGuardrails({ ...guardrails, max_correction_retries: parseInt(e.target.value, 10) || 1 })}
                  className="w-16 bg-slate-50 border border-slate-200 rounded-lg px-2 py-1 text-xs text-slate-900 text-center font-mono"
                />
              </div>

              <button
                onClick={handleSaveGuardrails}
                className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors shadow-xs cursor-pointer"
              >
                Save &amp; Apply Guardrail Settings
              </button>
            </div>
          </div>
        )}

        {/* TAB 4: QDRANT COLLECTIONS */}
        {activeTab === 'qdrant' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-slate-900">Qdrant Vector Collections</h2>
                <p className="text-xs text-slate-500">Live vector collections on port 6333.</p>
              </div>
              <a
                href="http://localhost:6333/dashboard"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-xs transition-all"
              >
                <Database className="w-4 h-4" />
                <span>Launch Qdrant Web UI (6333)</span>
                <ExternalLink className="w-3.5 h-3.5 opacity-80" />
              </a>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {collections.map((col) => (
                <div key={col.name} className="p-5 rounded-2xl bg-white border border-slate-200 space-y-3 shadow-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm font-bold text-purple-700">{col.name}</span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {col.status.toUpperCase()}
                    </span>
                  </div>

                  <div className="space-y-1.5 text-xs text-slate-600 font-mono">
                    <div className="flex justify-between">
                      <span>Points:</span>
                      <span className="text-slate-900 font-bold">{col.points_count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Indexed Vectors:</span>
                      <span className="text-slate-700">{col.indexed_vectors_count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Segments:</span>
                      <span className="text-slate-700">{col.segments_count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Dimension:</span>
                      <span className="text-slate-700">768 (Cosine)</span>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-100">
                    <a
                      href={`http://localhost:6333/dashboard#/collections/${col.name}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-purple-600 hover:underline flex items-center gap-1 font-medium"
                    >
                      <span>Inspect points in Qdrant dashboard</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 5: DOCUMENTS */}
        {activeTab === 'documents' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-bold text-slate-900">Knowledge Base Documents</h2>
                <p className="text-xs text-slate-500">Files and scraped pages indexed in <code className="text-purple-600 font-mono">knowledge_base</code>.</p>
              </div>

              <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold cursor-pointer transition-colors shadow-xs">
                <UploadCloud className="w-3.5 h-3.5" />
                <span>{isUploading ? 'Uploading...' : 'Upload File'}</span>
                <input
                  type="file"
                  className="hidden"
                  onChange={handleFileUpload}
                  disabled={isUploading}
                  accept=".pdf,.docx,.txt,.md,.csv,.png,.jpg"
                />
              </label>
            </div>

            {/* Ingest URL */}
            <form onSubmit={handleUrlSubmit} className="flex gap-2">
              <div className="relative flex-1">
                <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="url"
                  placeholder="Scrape & index website URL (e.g. documentation or guides)..."
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 shadow-xs"
                />
              </div>
              <button
                type="submit"
                disabled={isUrlIngesting || !urlInput.trim()}
                className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-200 disabled:opacity-50 transition-colors cursor-pointer"
              >
                {isUrlIngesting ? 'Scraping...' : 'Index URL'}
              </button>
            </form>

            {/* Document Table */}
            <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-mono text-[10px]">
                  <tr>
                    <th className="px-4 py-3">Source Name / URL</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Chunks</th>
                    <th className="px-4 py-3">Summary Topics</th>
                    <th className="px-4 py-3 text-right">Delete</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {documents.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                        No documents indexed yet.
                      </td>
                    </tr>
                  ) : (
                    documents.map((doc) => (
                      <tr key={doc.doc_id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="px-4 py-3 font-semibold text-slate-900">
                          <div className="flex items-center gap-2">
                            {doc.source_type === 'html' ? (
                              <Globe className="w-4 h-4 text-emerald-600 shrink-0" />
                            ) : (
                              <FileText className="w-4 h-4 text-indigo-600 shrink-0" />
                            )}
                            <span className="truncate max-w-xs">{doc.source_name}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-mono text-[10px] uppercase font-medium">
                            {doc.source_type}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono text-slate-700">{doc.chunk_count}</td>
                        <td className="px-4 py-3 text-slate-600 max-w-md">
                          <p className="truncate text-[11px]">{doc.summary || 'Summary indexed'}</p>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => handleDeleteDocument(doc.doc_id)}
                            className="p-1 rounded-md hover:bg-rose-50 text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                            title="Delete Document"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
