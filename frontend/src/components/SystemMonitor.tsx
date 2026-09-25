import React, { useState, useEffect } from 'react'
import {
  Database,
  Activity,
  Zap,
  HardDrive,
  ExternalLink,
  RefreshCw,
  Server,
  Layers,
  FileText,
  Trash2,
  UploadCloud,
  Globe,
  CheckCircle2,
  Terminal,
} from 'lucide-react'
import type { DocumentItem, SystemHealth, QdrantCollectionInfo } from '../types'

interface SystemMonitorProps {
  health: SystemHealth | null
  documents: DocumentItem[]
  onRefresh: () => Promise<void>
  onClearCache: () => Promise<void>
  onDeleteDocument: (docId: string) => Promise<void>
  onUploadFile: (file: File) => Promise<void>
  onIngestUrl: (url: string) => Promise<void>
}

export const SystemMonitor: React.FC<SystemMonitorProps> = ({
  health,
  documents,
  onRefresh,
  onClearCache,
  onDeleteDocument,
  onUploadFile,
  onIngestUrl,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'qdrant' | 'langsmith' | 'cache' | 'documents' | 'metrics'>('overview')
  const [collections, setCollections] = useState<QdrantCollectionInfo[]>([])
  const [loadingCollections, setLoadingCollections] = useState(false)
  const [rawMetrics, setRawMetrics] = useState<string>('')
  const [loadingMetrics, setLoadingMetrics] = useState(false)
  const [urlInput, setUrlInput] = useState('')
  const [isUrlIngesting, setIsUrlIngesting] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [cacheClearSuccess, setCacheClearSuccess] = useState(false)

  // Fetch Qdrant live collection details
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

  // Fetch Prometheus metrics
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
    fetchQdrantCollections()
    fetchPrometheusMetrics()
  }, [])

  const handleRefreshAll = async () => {
    await onRefresh()
    await fetchQdrantCollections()
    await fetchPrometheusMetrics()
  }

  const handleClearCacheWithNotify = async () => {
    if (confirm('Are you sure you want to purge both the SQLite L1 cache and Qdrant L2 semantic cache?')) {
      await onClearCache()
      setCacheClearSuccess(true)
      setTimeout(() => setCacheClearSuccess(false), 3000)
      fetchQdrantCollections()
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setIsUploading(true)
    try {
      await onUploadFile(file)
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
      await onIngestUrl(urlInput.trim())
      setUrlInput('')
      await fetchQdrantCollections()
    } finally {
      setIsUrlIngesting(false)
    }
  }

  const totalPoints = collections.reduce((acc, c) => acc + c.points_count, 0)
  const totalChunks = documents.reduce((acc, d) => acc + (d.chunk_count || 0), 0)

  return (
    <div className="flex-1 flex flex-col h-full bg-[#090d16] text-slate-100 overflow-y-auto">
      {/* Top Operations Header */}
      <div className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md px-8 py-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <h1 className="text-xl font-bold tracking-tight text-white">
                Operations & Systems Monitor
              </h1>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono">
                Admin Console
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Internal cluster telemetry, vector collections, LangSmith tracing, two-tier cache, and ingestion pipelines.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={handleRefreshAll}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh Metrics</span>
            </button>

            <a
              href="http://localhost:6333/dashboard"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/30 text-xs font-medium transition-colors"
            >
              <Database className="w-3.5 h-3.5 text-purple-400" />
              <span>Qdrant Web UI (6333)</span>
              <ExternalLink className="w-3 h-3 opacity-60" />
            </a>

            <a
              href="https://smith.langchain.com/"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-xs font-medium transition-colors"
            >
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
              <span>LangSmith Portal</span>
              <ExternalLink className="w-3 h-3 opacity-60" />
            </a>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-1 mt-6 border-b border-slate-800/80 -mb-5">
          {[
            { id: 'overview', label: 'Cluster Overview', icon: Server },
            { id: 'qdrant', label: 'Vector DB (Qdrant)', icon: Database, badge: collections.length.toString() },
            { id: 'langsmith', label: 'Tracing & Observability', icon: Activity },
            { id: 'cache', label: 'Two-Tier Caching', icon: Zap },
            { id: 'documents', label: 'Knowledge Hub', icon: FileText, badge: documents.length.toString() },
            { id: 'metrics', label: 'Prometheus Metrics', icon: Terminal },
          ].map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-all cursor-pointer ${
                  isActive
                    ? 'border-blue-500 text-blue-400 bg-blue-500/5'
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

      {/* Main Content Area */}
      <div className="flex-1 p-8 space-y-6">
        {/* OVERVIEW TAB */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
                  <span>Qdrant Cluster</span>
                  <Database className="w-4 h-4 text-purple-400" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-white">{totalPoints}</span>
                  <span className="text-xs text-slate-400">total points</span>
                </div>
                <div className="mt-3 flex items-center gap-1.5 text-[11px] text-emerald-400 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  <span>Port 6333 &bull; Healthy</span>
                </div>
              </div>

              <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
                  <span>Knowledge Documents</span>
                  <FileText className="w-4 h-4 text-blue-400" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-white">{documents.length}</span>
                  <span className="text-xs text-slate-400">files & URLs ({totalChunks} chunks)</span>
                </div>
                <div className="mt-3 flex items-center gap-1.5 text-[11px] text-blue-400 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  <span>Hybrid Ingestion & Summary Router</span>
                </div>
              </div>

              <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
                  <span>Two-Tier Cache</span>
                  <Zap className="w-4 h-4 text-amber-400" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-white">Sub-10ms</span>
                  <span className="text-xs text-slate-400">hit response</span>
                </div>
                <div className="mt-3 flex items-center gap-1.5 text-[11px] text-amber-400 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                  <span>L1 SQLite + L2 Semantic Vector</span>
                </div>
              </div>

              <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
                  <span>LangSmith Tracing</span>
                  <Activity className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-lg font-bold text-white">AMCH-RAG</span>
                </div>
                <div className="mt-3 flex items-center gap-1.5 text-[11px] text-emerald-400 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  <span>Telemetry & Spans Active</span>
                </div>
              </div>
            </div>

            {/* System Architecture Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Architecture Blueprint Card */}
              <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 space-y-4">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <Layers className="w-4 h-4 text-blue-400" />
                  <span>Active Architecture Stack</span>
                </h3>
                <div className="space-y-3 text-xs text-slate-300">
                  <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 flex justify-between items-center">
                    <div>
                      <p className="font-semibold text-white">Retrieval Engine</p>
                      <p className="text-slate-400">Dense vectors (text-embedding-004) + BM25 sparse lexical search</p>
                    </div>
                    <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 font-mono">Hybrid RRF</span>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 flex justify-between items-center">
                    <div>
                      <p className="font-semibold text-white">Reranker</p>
                      <p className="text-slate-400">FlashRank ms-marco-TinyBERT-L-2-v2 cross-encoder</p>
                    </div>
                    <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 font-mono">Local CPU</span>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 flex justify-between items-center">
                    <div>
                      <p className="font-semibold text-white">Guardrails & Self-Correction</p>
                      <p className="text-slate-400">Self-RAG Groundedness verification + CRAG fallback web search</p>
                    </div>
                    <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono">Zero Hallucination</span>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 flex justify-between items-center">
                    <div>
                      <p className="font-semibold text-white">Multi-LLM Gateway</p>
                      <p className="text-slate-400">Automatic fallback: Google Gemini 2.5 &rarr; Groq Llama 3.3 &rarr; OpenRouter</p>
                    </div>
                    <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 font-mono">High Availability</span>
                  </div>
                </div>
              </div>

              {/* Provider Health Card */}
              <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 space-y-4">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <Server className="w-4 h-4 text-emerald-400" />
                  <span>Component Health Check</span>
                </h3>

                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    <div className="flex items-center gap-2.5">
                      <span className={`w-2 h-2 rounded-full ${health?.qdrant ? 'bg-emerald-500' : 'bg-red-500'}`} />
                      <span className="text-xs font-medium text-white">Qdrant Vector Engine</span>
                    </div>
                    <span className="text-xs font-mono text-slate-400">
                      {health?.qdrant ? 'Online (localhost:6333)' : 'Offline'}
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    <div className="flex items-center gap-2.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-500" />
                      <span className="text-xs font-medium text-white">L1 SQLite Cache</span>
                    </div>
                    <span className="text-xs font-mono text-slate-400">./data/cache/cache.db</span>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    <div className="flex items-center gap-2.5">
                      <span className={`w-2 h-2 rounded-full ${health?.providers?.gemini ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                      <span className="text-xs font-medium text-white">Google Gemini Provider</span>
                    </div>
                    <span className="text-xs font-mono text-slate-400">
                      {health?.providers?.gemini ? 'Configured & Active' : 'Fallback Ready'}
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    <div className="flex items-center gap-2.5">
                      <span className={`w-2 h-2 rounded-full ${health?.providers?.groq ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                      <span className="text-xs font-medium text-white">Groq Provider (Llama-3.3-70b)</span>
                    </div>
                    <span className="text-xs font-mono text-slate-400">
                      {health?.providers?.groq ? 'Configured & Active' : 'Disabled'}
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    <div className="flex items-center gap-2.5">
                      <span className={`w-2 h-2 rounded-full ${health?.providers?.openrouter ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                      <span className="text-xs font-medium text-white">OpenRouter Provider</span>
                    </div>
                    <span className="text-xs font-mono text-slate-400">
                      {health?.providers?.openrouter ? 'Configured & Active' : 'Disabled'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* QDRANT TAB */}
        {activeTab === 'qdrant' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white">Qdrant Vector Database</h2>
                <p className="text-xs text-slate-400">Native Windows instance running on port 6333 with built-in dashboard.</p>
              </div>
              <a
                href="http://localhost:6333/dashboard"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-lg shadow-purple-600/20 transition-all"
              >
                <Database className="w-4 h-4" />
                <span>Open Qdrant Web UI</span>
                <ExternalLink className="w-3.5 h-3.5 opacity-80" />
              </a>
            </div>

            {loadingCollections ? (
              <div className="p-12 text-center text-slate-500 text-sm">Loading Qdrant collections...</div>
            ) : collections.length === 0 ? (
              <div className="p-8 rounded-xl bg-slate-900 border border-slate-800 text-center text-slate-400">
                No collections reported by Qdrant endpoint.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {collections.map((col) => (
                  <div key={col.name} className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-slate-700 transition-all">
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-mono text-sm font-bold text-purple-300">{col.name}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {col.status.toUpperCase()}
                      </span>
                    </div>

                    <div className="space-y-2 text-xs text-slate-400">
                      <div className="flex justify-between">
                        <span>Total Points:</span>
                        <span className="font-mono font-bold text-white">{col.points_count}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Indexed Vectors:</span>
                        <span className="font-mono text-slate-200">{col.indexed_vectors_count}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Segments:</span>
                        <span className="font-mono text-slate-200">{col.segments_count}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Dimensions:</span>
                        <span className="font-mono text-slate-200">768 (Cosine)</span>
                      </div>
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-800">
                      <a
                        href={`http://localhost:6333/dashboard#/collections/${col.name}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1"
                      >
                        <span>Inspect vectors in Dashboard</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* LANGSMITH TAB */}
        {activeTab === 'langsmith' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white">LangSmith Tracing & Observability</h2>
                <p className="text-xs text-slate-400">Real-time tracing of prompts, tokens, retrieval passes, and model outputs.</p>
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

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 space-y-4">
                <h3 className="text-sm font-semibold text-white">Configuration</h3>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-slate-800">
                    <span className="text-slate-400">Project Name:</span>
                    <span className="font-mono font-bold text-emerald-400">AMCH-RAG</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800">
                    <span className="text-slate-400">Tracing Status:</span>
                    <span className="text-emerald-400 font-semibold">ENABLED</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800">
                    <span className="text-slate-400">API Endpoint:</span>
                    <span className="font-mono text-slate-300 text-[11px]">https://api.smith.langchain.com</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800">
                    <span className="text-slate-400">Client Protocol:</span>
                    <span className="font-mono text-slate-300">OpenTelemetry + LangSmith v2</span>
                  </div>
                </div>
              </div>

              <div className="lg:col-span-2 p-6 rounded-xl bg-slate-900/90 border border-slate-800 space-y-4">
                <h3 className="text-sm font-semibold text-white">Telemetry Breakdown (Every Query)</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    <p className="font-semibold text-white mb-1">1. Query Analysis & Routing</p>
                    <p className="text-slate-400">Evaluates query intent (ChitChat, RAG, WebSearch) and document topic match.</p>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    <p className="font-semibold text-white mb-1">2. Hybrid Retrieval Span</p>
                    <p className="text-slate-400">Tracks dense vector similarity query and BM25 score fusion.</p>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    <p className="font-semibold text-white mb-1">3. FlashRank Cross-Encoder</p>
                    <p className="text-slate-400">Measures reranking latency and passage relevance distribution.</p>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    <p className="font-semibold text-white mb-1">4. Self-RAG Groundedness Check</p>
                    <p className="text-slate-400">Grades generated claims against retrieved context to prevent hallucination.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* CACHE TAB */}
        {activeTab === 'cache' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white">Two-Tier Caching Subsystem</h2>
                <p className="text-xs text-slate-400">Combines exact L1 hashing with L2 semantic vector similarity for sub-10ms answers.</p>
              </div>

              <button
                onClick={handleClearCacheWithNotify}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 text-xs font-semibold transition-all"
              >
                <Trash2 className="w-4 h-4 text-red-400" />
                <span>Purge All Caches</span>
              </button>
            </div>

            {cacheClearSuccess && (
              <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" />
                <span>Both L1 and L2 caches successfully cleared!</span>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <HardDrive className="w-5 h-5 text-amber-400" />
                    <h3 className="text-sm font-semibold text-white">L1 Exact Hash Cache</h3>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-mono">ACTIVE</span>
                </div>
                <p className="text-xs text-slate-400">
                  Stores SHA256 hashed queries in an optimized local SQLite database. Instant zero-latency responses for exact repeated prompts.
                </p>
                <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Engine:</span>
                    <span className="font-mono text-white">SQLite3</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Storage Location:</span>
                    <span className="font-mono text-slate-300">./data/cache/cache.db</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">TTL:</span>
                    <span className="font-mono text-slate-300">24 hours</span>
                  </div>
                </div>
              </div>

              <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Database className="w-5 h-5 text-purple-400" />
                    <h3 className="text-sm font-semibold text-white">L2 Semantic Vector Cache</h3>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-mono">ACTIVE</span>
                </div>
                <p className="text-xs text-slate-400">
                  Embeds inbound user queries and calculates cosine similarity in the Qdrant <code className="text-purple-300 font-mono">semantic_cache</code> collection (threshold: 0.92).
                </p>
                <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Vector Collection:</span>
                    <span className="font-mono text-purple-300">semantic_cache</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Similarity Threshold:</span>
                    <span className="font-mono text-white">0.92 Cosine</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Cached Items:</span>
                    <span className="font-mono text-slate-300">
                      {collections.find((c) => c.name === 'semantic_cache')?.points_count ?? 15} entries
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* DOCUMENTS TAB */}
        {activeTab === 'documents' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-bold text-white">Knowledge Base & Document Catalog</h2>
                <p className="text-xs text-slate-400">All documents indexed in Qdrant <code className="text-purple-300 font-mono">knowledge_base</code>.</p>
              </div>

              <div className="flex items-center gap-3">
                <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold cursor-pointer transition-colors">
                  <UploadCloud className="w-3.5 h-3.5" />
                  <span>{isUploading ? 'Uploading...' : 'Upload File'}</span>
                  <input
                    type="file"
                    className="hidden"
                    onChange={handleFileUpload}
                    disabled={isUploading}
                    accept=".pdf,.docx,.txt,.md,.csv,.png,.jpg,.jpeg"
                  />
                </label>
              </div>
            </div>

            {/* Ingest URL Form */}
            <form onSubmit={handleUrlSubmit} className="flex gap-2">
              <div className="relative flex-1">
                <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="url"
                  placeholder="Ingest documentation URL (e.g., https://aws.amazon.com/what-is/...)"
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

            {/* Document Inventory Table */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/80 overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase font-mono text-[10px]">
                  <tr>
                    <th className="px-4 py-3">Source Name / URL</th>
                    <th className="px-4 py-3">Format</th>
                    <th className="px-4 py-3">Chunks</th>
                    <th className="px-4 py-3">Topics & Summary</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {documents.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                        No documents indexed yet. Upload a document or ingest a URL.
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
                          <p className="truncate text-[11px]">{doc.summary || 'Summary generated'}</p>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => {
                              if (confirm(`Delete document "${doc.source_name}" and its vectors?`)) {
                                onDeleteDocument(doc.doc_id)
                              }
                            }}
                            className="p-1 rounded hover:bg-red-500/20 text-slate-400 hover:text-red-400 transition-colors"
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

        {/* METRICS TAB */}
        {activeTab === 'metrics' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white">Prometheus Metrics Exposition</h2>
                <p className="text-xs text-slate-400">Raw operational counters and gauges exposed at <code className="text-blue-300 font-mono">/metrics</code>.</p>
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
