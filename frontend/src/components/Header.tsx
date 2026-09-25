import React from 'react'
import { Activity, ShieldCheck, Zap, Database, ExternalLink, Sparkles, RotateCcw } from 'lucide-react'
import type { SystemHealth } from '../types'

interface HeaderProps {
  health: SystemHealth | null
  sessionId: string
  onResetSession: () => void
  onToggleSidebar: () => void
  isSidebarOpen: boolean
}

export const Header: React.FC<HeaderProps> = ({
  health,
  sessionId,
  onResetSession,
  onToggleSidebar,
  isSidebarOpen,
}) => {
  return (
    <header className="h-16 border-b border-slate-800/80 glass-panel px-6 flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-4">
        <button
          onClick={onToggleSidebar}
          className="md:hidden p-2 rounded-lg bg-slate-800/60 hover:bg-slate-700/60 text-slate-300 transition-colors"
          title={isSidebarOpen ? 'Close Knowledge Hub' : 'Open Knowledge Hub'}
        >
          <Database className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <span className="absolute -top-0.5 -right-0.5 w-3 h-3 bg-emerald-500 border-2 border-slate-900 rounded-full animate-pulse-dot" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                AMCH-RAG
              </span>
              <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                Enterprise
              </span>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">
              Multi-Modal Self-RAG &bull; CRAG &bull; Two-Tier Cache &bull; LangSmith
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* System telemetry badges */}
        <div className="hidden lg:flex items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/60 border border-slate-800 text-slate-300">
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            <span>Qdrant: {health?.qdrant ? 'Live (6333)' : 'Connecting'}</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/60 border border-slate-800 text-slate-300">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>Cache: SQLite + Qdrant</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/60 border border-slate-800 text-slate-300">
            <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
            <span>Guardrails: Active</span>
          </div>
        </div>

        {/* Quick Links & Actions */}
        <div className="flex items-center gap-1.5 border-l border-slate-800/80 pl-3">
          <button
            onClick={onResetSession}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-300 border border-blue-500/30 text-xs font-medium transition-all"
            title={`Start a clean session (Active ID: ${sessionId})`}
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">New Chat</span>
          </button>

          <a
            href="http://localhost:6333/dashboard"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/30 text-xs font-medium transition-all"
            title="Open Qdrant Web Dashboard"
          >
            <Database className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Qdrant UI</span>
            <ExternalLink className="w-3 h-3 opacity-60" />
          </a>

          <a
            href="https://smith.langchain.com/"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-medium transition-all"
            title="Open LangSmith Observability"
          >
            <Activity className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">LangSmith</span>
            <ExternalLink className="w-3 h-3 opacity-60" />
          </a>
        </div>
      </div>
    </header>
  )
}
