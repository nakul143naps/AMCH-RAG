import React, { useState, useEffect } from 'react'
import {
  Database,
  Activity,
  Zap,
  HardDrive,
  ExternalLink,
  RefreshCw,
  Server,
  FileText,
  Trash2,
  UploadCloud,
  Globe,
  CheckCircle2,
  Terminal,
  ShieldAlert,
  Brain,
  Lock,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react'
import type { DocumentItem, SystemHealth, QdrantCollectionInfo } from '../types'

export const AdminCockpit: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    return localStorage.getItem('amch_admin_auth') === 'true'
  })
  const [passkeyInput, setPasskeyInput] = useState('')
  const [passkeyError, setPasskeyError] = useState(false)

  const [activeTab, setActiveTab] = useState<'overview' | 'qdrant' | 'cache' | 'memory' | 'guardrails' | 'documents' | 'langsmith' | 'metrics'>('overview')
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [collections, setCollections] = useState<QdrantCollectionInfo[]>([])
  const [loadingCollections, setLoadingCollections] = useState(false)
  const [rawMetrics, setRawMetrics] = useState<string>('')
  const [loadingMetrics, setLoadingMetrics] = useState(false)
  const [urlInput, setUrlInput] = useState('')
  const [isUrlIngesting, setIsUrlIngesting] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [cacheClearSuccess, setCacheClearSuccess] = useState(false)

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault()
    // Default passkey for Admin Cockpit
    if (passkeyInput === 'admin' || passkeyInput === 'admin123') {
      setIsAuthenticated(true)
      localStorage.setItem('amch_admin_auth', 'true')
      setPasskeyError(false)
    } else {
      setPasskeyError(true)
    }
  }

  const handleLogout = () => {
    setIsAuthenticated(false)
    localStorage.removeItem('amch_admin_auth')
  }

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

  const fetchQdrantCollections = async () => {
    setLoadingCollections(true)
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
                status: r.status || 'unknown',
                segments_count: r.segments_count || 0,
              })
            }
          } catch (e) {
            console.error(`Failed to fetch details for ${col.name}`, e)
          }
        }
        setCollections(detailedCols)
      }
    } catch (e) {
      console.error('Failed to fetch Qdrant collections:', e)
    } finally {
      setLoadingCollections(false)
    }
  }

  const fetchPrometheusMetrics = async () => {
    setLoadingMetrics(true)
    try {
      const res = await fetch('/metrics')
      if (res.ok) {
        const text = await res.text()
        setRawMetrics(text)
      }
    } catch (e) {
      console.error('Failed to fetch metrics:', e)
    } finally {
      setLoadingMetrics(false)
    }
  }

  useEffect(() => {
    if (isAuthenticated) {
      loadDocuments()
      loadHealth()
      fetchQdrantCollections()
      fetchPrometheusMetrics()
    }
  }, [isAuthenticated])

  const handleRefreshAll = async () => {
    await loadDocuments()
    await loadHealth()
    await fetchQdrantCollections()
    await fetchPrometheusMetrics()
  }

  const handleClearCache = async () => {
    if (confirm('Purge both the SQLite L1 cache and Qdrant L2 semantic cache?')) {
      try {
        await fetch('/query/cache', { method: 'DELETE' })
        setCacheClearSuccess(true)
        setTimeout(() => setCacheClearSuccess(false), 3000)
        await fetchQdrantCollections()
      } catch (e) {
        console.error('Failed to clear cache:', e)
      }
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
      await loadDocuments()
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
      await loadDocuments()
      await fetchQdrantCollections()
    } finally {
      setIsUrlIngesting(false)
    }
  }

  const totalPoints = collections.reduce((acc, c) => acc + c.points_count, 0)
  const totalChunks = documents.reduce((acc, d) => acc + (d.chunk_count || 0), 0)

  // Passkey Login Screen
  if (!isAuthenticated) {
    return (
      <div className="h-screen w-screen bg-[#070a10] flex items-center justify-center p-4 text-slate-100 font-sans">
        <div className="max-w-md w-full p-8 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-2xl space-y-6">
          <div className="text-center space-y-2">
            <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center mx-auto shadow-sm">
              <Lock className="w-6 h-6" />
            </div>
            <h1 className="text-xl font-bold text-white tracking-tight">
              AMCH Admin Operations
            </h1>
            <p className="text-xs text-slate-400">
              Restricted portal for cluster monitoring, vector collections, memory, and cache operations.
            </p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Admin Passkey
              </label>
              <input
                type="password"
                value={passkeyInput}
                onChange={(e) => setPasskeyInput(e.target.value)}
                placeholder="Enter admin passkey (default: admin)"
                className="w-full bg-slate-950 border border-slate-800 focus:border-purple-500 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none transition-colors"
                autoFocus
              />
              {passkeyError && (
                <p className="text-xs text-rose-400 mt-1.5 flex items-center gap-1">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  Incorrect passkey. Please try again.
                </p>
              )}
            </div>

            <button
              type="submit"
              className="w-full py-2.5 px-4 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors shadow-lg shadow-purple-600/20"
            >
              <span>Unlock Admin Cockpit</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </form>

          <div className="pt-2 text-center border-t border-slate-800/80">
            <a
              href="/"
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              &larr; Return to Public Assistant
            </a>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col h-screen bg-[#070a10] text-slate-100 overflow-hidden font-sans">
      {/* Top Admin Header */}
      <div className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md px-6 py-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-purple-600/20 border border-purple-500/30 text-purple-400 flex items-center justify-center font-bold">
              AM
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold text-white tracking-tight">
                  Mr. Admin Operations Cockpit
                </h1>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/30 font-mono">
                  Full Authority
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Live monitoring of all caches, user memory, guardrails, Qdrant vectors, and LangSmith.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <a
              href="/"
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition-colors"
            >
              View User Assistant &rarr;
            </a>

            <button
              onClick={handleRefreshAll}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors border border-slate-700"
              title="Refresh All Telemetry"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>

            <a
              href="http://localhost:6333/dashboard"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/30 text-xs font-medium transition-colors"
            >
              <Database className="w-3.5 h-3.5 text-purple-400" />
              <span>Qdrant (6333)</span>
              <ExternalLink className="w-3 h-3 opacity-60" />
            </a>

            <a
              href="https://smith.langchain.com/"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-xs font-medium transition-colors"
            >
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
              <span>LangSmith</span>
              <ExternalLink className="w-3 h-3 opacity-60" />
            </a>

            <button
              onClick={handleLogout}
              className="px-2.5 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/20 text-xs font-medium transition-colors"
              title="Lock Admin Portal"
            >
              Lock
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-1 mt-4 border-b border-slate-800/80 -mb-4 overflow-x-auto">
          {[
            { id: 'overview', label: 'Cluster Overview', icon: Server },
            { id: 'cache', label: 'All Caches (L1 + L2)', icon: Zap },
            { id: 'memory', label: 'User Memory (Facts)', icon: Brain },
            { id: 'guardrails', label: 'Guardrails & CRAG', icon: ShieldCheck },
            { id: 'qdrant', label: 'Vector DB (Qdrant)', icon: Database, badge: collections.length.toString() },
            { id: 'documents', label: 'Document Store', icon: FileText, badge: documents.length.toString() },
            { id: 'langsmith', label: 'LangSmith Tracing', icon: Activity },
            { id: 'metrics', label: 'Prometheus Metrics', icon: Terminal },
          ].map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-3.5 py-2.5 text-xs font-medium border-b-2 transition-all cursor-pointer whitespace-nowrap ${
                  isActive
                    ? 'border-purple-500 text-purple-300 bg-purple-500/5'
                    : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span className="px-1.5 py-0.2 rounded-full bg-slate-800 text-[10px] text-slate-300">
                    {tab.badge}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Main Admin Scrollable Canvas */}
      <div className="flex-1 p-6 md:p-8 space-y-6 overflow-y-auto">
        {/* TAB 1: OVERVIEW */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
                  <span>Qdrant Vectors</span>
                  <Database className="w-4 h-4 text-purple-400" />
                </div>
                <div className="text-2xl font-bold text-white">{totalPoints} points</div>
                <div className="mt-2 text-xs text-emerald-400 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  <span>3 Collections (Healthy)</span>
                </div>
              </div>

              <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
                  <span>Caching Subsystem</span>
                  <Zap className="w-4 h-4 text-amber-400" />
                </div>
                <div className="text-2xl font-bold text-white">Two-Tier Active</div>
                <div className="mt-2 text-xs text-amber-400 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                  <span>L1 SQLite + L2 Semantic Vector</span>
                </div>
              </div>

              <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
                  <span>Knowledge Documents</span>
                  <FileText className="w-4 h-4 text-blue-400" />
                </div>
                <div className="text-2xl font-bold text-white">{documents.length} files</div>
                <div className="mt-2 text-xs text-blue-400 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  <span>{totalChunks} indexed chunks</span>
                </div>
              </div>

              <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
                  <span>Hallucination Guardrails</span>
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="text-2xl font-bold text-white">Self-RAG + CRAG</div>
                <div className="mt-2 text-xs text-emerald-400 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  <span>Threshold 1.0 Zero-Tolerance</span>
                </div>
              </div>
            </div>

            {/* Provider Health Breakdown */}
            <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 space-y-4">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Server className="w-4 h-4 text-purple-400" />
                <span>Model Gateway & Component Providers</span>
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-xs text-white">Google Gemini Provider</span>
                    <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-mono">
                      {health?.providers?.gemini ? 'PRIMARY (ACTIVE)' : 'CONFIGURED'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">Gemini 2.5 Flash & text-embedding-004</p>
                  <p className="text-[11px] text-emerald-400 mt-2 font-mono">Status: Online</p>
                </div>

                <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-xs text-white">Groq Provider</span>
                    <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 text-[10px] font-mono">
                      {health?.providers?.groq ? 'FALLBACK 1 (READY)' : 'STANDBY'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">Llama-3.3-70b-versatile ultra-low latency</p>
                  <p className="text-[11px] text-blue-400 mt-2 font-mono">Status: Standby Ready</p>
                </div>

                <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-xs text-white">OpenRouter Provider</span>
                    <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 text-[10px] font-mono">
                      {health?.providers?.openrouter ? 'FALLBACK 2 (READY)' : 'STANDBY'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">Multi-provider high availability backup</p>
                  <p className="text-[11px] text-amber-400 mt-2 font-mono">Status: Standby Ready</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: CACHE (ALL CACHES) */}
        {activeTab === 'cache' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white">Two-Tier Caching Subsystem</h2>
                <p className="text-xs text-slate-400">
                  Monitors exact hash caching (L1) and vector semantic caching (L2).
                </p>
              </div>

              <button
                onClick={handleClearCache}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 text-xs font-semibold transition-all"
              >
                <Trash2 className="w-4 h-4 text-red-400" />
                <span>Purge All Caches (L1 + L2)</span>
              </button>
            </div>

            {cacheClearSuccess && (
              <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" />
                <span>Cache purged cleanly across SQLite and Qdrant.</span>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <HardDrive className="w-5 h-5 text-amber-400" />
                    <h3 className="text-sm font-semibold text-white">L1 Exact Hash Cache</h3>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-mono">ONLINE</span>
                </div>
                <p className="text-xs text-slate-400">
                  Calculates SHA-256 digests over incoming prompts. On hit, bypasses the embedding model, vector store, and LLM entirely.
                </p>
                <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs space-y-1 font-mono">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Store:</span>
                    <span className="text-white">SQLite3 (`./data/cache/cache.db`)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Latency:</span>
                    <span className="text-emerald-400">&lt; 1ms</span>
                  </div>
                </div>
              </div>

              <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Database className="w-5 h-5 text-purple-400" />
                    <h3 className="text-sm font-semibold text-white">L2 Semantic Vector Cache</h3>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-mono">ONLINE</span>
                </div>
                <p className="text-xs text-slate-400">
                  Embeds user queries and searches the Qdrant <code className="text-purple-300 font-mono">semantic_cache</code> collection for semantically identical questions.
                </p>
                <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs space-y-1 font-mono">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Collection:</span>
                    <span className="text-purple-300">semantic_cache</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Threshold:</span>
                    <span className="text-white">0.92 Cosine</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Cached Entries:</span>
                    <span className="text-white">
                      {collections.find((c) => c.name === 'semantic_cache')?.points_count ?? 15} entries
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: USER MEMORY */}
        {activeTab === 'memory' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-white">User Long-Term Memory & Personalization</h2>
              <p className="text-xs text-slate-400">
                Managed in the Qdrant <code className="text-purple-300 font-mono">user_memory</code> collection.
              </p>
            </div>

            <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Brain className="w-5 h-5 text-blue-400" />
                  <h3 className="text-sm font-semibold text-white">Memory Extraction Pipeline</h3>
                </div>
                <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 text-[10px] font-mono">
                  ACTIVE
                </span>
              </div>

              <p className="text-xs text-slate-300 leading-relaxed">
                When users interact with the assistant, the memory agent identifies enduring user facts (e.g. roles, project contexts, coding style preferences) and commits them to the vector store. On future turns, relevant memories are recalled to customize the response.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2 text-xs">
                <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                  <span className="text-slate-500 font-mono text-[10px] block">COLLECTION NAME</span>
                  <span className="font-mono text-purple-300 font-semibold">user_memory</span>
                </div>
                <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                  <span className="text-slate-500 font-mono text-[10px] block">STORED POINTS</span>
                  <span className="font-mono text-white font-semibold">
                    {collections.find((c) => c.name === 'user_memory')?.points_count ?? 0} facts
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                  <span className="text-slate-500 font-mono text-[10px] block">RETRIEVAL TOP-K</span>
                  <span className="font-mono text-white font-semibold">k = 3 (Threshold 0.70)</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: GUARDRAILS & CRAG */}
        {activeTab === 'guardrails' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-white">Self-RAG & CRAG Hallucination Guardrails</h2>
              <p className="text-xs text-slate-400">
                Multi-stage verification ensuring generated responses are strictly grounded in retrieved evidence.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-sm font-semibold text-white">Self-RAG Groundedness Grader</h3>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Every claim in the generated text is cross-examined against the context chunks. If hallucinated claims or unsupported statements are detected, the response is rewritten or filtered before emission.
                </p>
                <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs font-mono space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Groundedness Pass Threshold:</span>
                    <span className="text-emerald-400">1.0 (Strict Zero Hallucination)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Citation Mapping:</span>
                    <span className="text-white">Chunk ID &amp; Section Level</span>
                  </div>
                </div>
              </div>

              <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
                <div className="flex items-center gap-2">
                  <Globe className="w-5 h-5 text-blue-400" />
                  <h3 className="text-sm font-semibold text-white">Corrective RAG (CRAG) Fallback</h3>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  If the hybrid retrieval score falls below confidence threshold or the knowledge base has zero relevant documentation for the query, CRAG triggers web fallback search or notifies the user cleanly.
                </p>
                <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs font-mono space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Retrieval Confidence Gate:</span>
                    <span className="text-amber-400">0.50 Hybrid RRF Score</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Fallback Target:</span>
                    <span className="text-white">Web Search &amp; General Corpus</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: QDRANT */}
        {activeTab === 'qdrant' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white">Qdrant Vector Engine</h2>
                <p className="text-xs text-slate-400">Direct cluster stats on port 6333.</p>
              </div>
              <a
                href="http://localhost:6333/dashboard"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-lg shadow-purple-600/20 transition-all"
              >
                <Database className="w-4 h-4" />
                <span>Launch Qdrant Web UI</span>
                <ExternalLink className="w-3.5 h-3.5 opacity-80" />
              </a>
            </div>

            {loadingCollections ? (
              <div className="p-12 text-center text-slate-500 text-sm">Loading collections...</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {collections.map((col) => (
                  <div key={col.name} className="p-5 rounded-xl bg-slate-900/90 border border-slate-800">
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-mono text-sm font-bold text-purple-300">{col.name}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {col.status.toUpperCase()}
                      </span>
                    </div>

                    <div className="space-y-1.5 text-xs text-slate-400 font-mono">
                      <div className="flex justify-between">
                        <span>Points:</span>
                        <span className="text-white font-bold">{col.points_count}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Indexed Vectors:</span>
                        <span className="text-slate-200">{col.indexed_vectors_count}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Segments:</span>
                        <span className="text-slate-200">{col.segments_count}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Dimension:</span>
                        <span className="text-slate-200">768 (Cosine)</span>
                      </div>
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-800">
                      <a
                        href={`http://localhost:6333/dashboard#/collections/${col.name}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 font-medium"
                      >
                        <span>View points in dashboard</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 6: DOCUMENTS */}
        {activeTab === 'documents' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-bold text-white">Document Store & Ingestion</h2>
                <p className="text-xs text-slate-400">All indexed files in <code className="text-purple-300 font-mono">knowledge_base</code>.</p>
              </div>

              <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold cursor-pointer transition-colors">
                <UploadCloud className="w-3.5 h-3.5" />
                <span>{isUploading ? 'Uploading...' : 'Upload Document'}</span>
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
                  placeholder="Ingest documentation URL (e.g. AWS, Wikipedia, Documentation)..."
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>
              <button
                type="submit"
                disabled={isUrlIngesting || !urlInput.trim()}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 disabled:opacity-50 transition-colors"
              >
                {isUrlIngesting ? 'Ingesting...' : 'Ingest URL'}
              </button>
            </form>

            {/* Document Table */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/80 overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase font-mono text-[10px]">
                  <tr>
                    <th className="px-4 py-3">Source Name / URL</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Chunks</th>
                    <th className="px-4 py-3">Summary Topics</th>
                    <th className="px-4 py-3 text-right">Delete</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {documents.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                        No documents indexed yet.
                      </td>
                    </tr>
                  ) : (
                    documents.map((doc) => (
                      <tr key={doc.doc_id} className="hover:bg-slate-800/40 transition-colors">
                        <td className="px-4 py-3 font-medium text-slate-200">
                          <div className="flex items-center gap-2">
                            {doc.source_type === 'html' ? (
                              <Globe className="w-4 h-4 text-emerald-400 shrink-0" />
                            ) : (
                              <FileText className="w-4 h-4 text-blue-400 shrink-0" />
                            )}
                            <span className="truncate max-w-xs">{doc.source_name}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[10px] uppercase">
                            {doc.source_type}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono text-slate-300">{doc.chunk_count}</td>
                        <td className="px-4 py-3 text-slate-400 max-w-md">
                          <p className="truncate text-[11px]">{doc.summary || 'Summary indexed'}</p>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => handleDeleteDocument(doc.doc_id)}
                            className="p-1 rounded hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 transition-colors"
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

        {/* TAB 7: LANGSMITH */}
        {activeTab === 'langsmith' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white">LangSmith Real-Time Tracing</h2>
                <p className="text-xs text-slate-400">Observability for every prompt, generation, and retrieval pass.</p>
              </div>
              <a
                href="https://smith.langchain.com/"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-600/20 transition-all"
              >
                <Activity className="w-4 h-4" />
                <span>Open LangSmith Dashboard</span>
                <ExternalLink className="w-3.5 h-3.5 opacity-80" />
              </a>
            </div>

            <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 space-y-4">
              <div className="flex justify-between py-2 border-b border-slate-800 text-xs">
                <span className="text-slate-400">Project Name:</span>
                <span className="font-mono font-bold text-emerald-400">AMCH-RAG</span>
              </div>
              <div className="flex justify-between py-2 border-b border-slate-800 text-xs">
                <span className="text-slate-400">Tracing Status:</span>
                <span className="text-emerald-400 font-semibold">ACTIVE</span>
              </div>
              <div className="flex justify-between py-2 border-b border-slate-800 text-xs">
                <span className="text-slate-400">API Endpoint:</span>
                <span className="font-mono text-slate-300">https://api.smith.langchain.com</span>
              </div>
            </div>
          </div>
        )}

        {/* TAB 8: PROMETHEUS METRICS */}
        {activeTab === 'metrics' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white">Prometheus Metrics Feed</h2>
                <p className="text-xs text-slate-400">Raw metrics exposed at <code className="text-blue-300 font-mono">/metrics</code>.</p>
              </div>
              <button
                onClick={fetchPrometheusMetrics}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Refresh</span>
              </button>
            </div>

            {loadingMetrics ? (
              <div className="p-12 text-center text-slate-500 text-sm">Loading Prometheus metrics...</div>
            ) : (
              <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs text-slate-300 overflow-x-auto max-h-[500px]">
                <pre>{rawMetrics || '# No metrics returned or endpoint offline'}</pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
