import React from 'react'
import { Sparkles, Plus, PanelLeft } from 'lucide-react'

interface UserHeaderProps {
  onResetSession: () => void
  onToggleSidebar: () => void
  isSidebarOpen: boolean
  activeTitle?: string
  isLoading?: boolean
  docCount?: number
}

export const UserHeader: React.FC<UserHeaderProps> = ({
  onResetSession,
  onToggleSidebar,
  isSidebarOpen,
  activeTitle,
  isLoading,
  docCount = 0,
}) => {
  return (
    <header className="h-16 border-b border-slate-200 bg-white/95 backdrop-blur-md px-4 md:px-6 flex items-center justify-between sticky top-0 z-30 select-none shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
      {/* Left side: Sidebar Toggle & Brand */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onToggleSidebar}
          className="p-2 rounded-xl text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer shrink-0"
          title={isSidebarOpen ? 'Collapse sidebar' : 'Open chat history'}
        >
          <PanelLeft className="w-4 h-4" />
        </button>

        {/* Project Branding */}
        <div className="flex items-center gap-2.5 shrink-0">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center text-white shadow-xs">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h1 className="font-extrabold text-sm md:text-base text-slate-900 tracking-tight">
                AMCH-RAG
              </h1>
              <span className="hidden sm:inline-block text-[10px] font-semibold uppercase px-1.5 py-0.2 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200">
                Assistant
              </span>
            </div>
            <p className="text-[10px] text-slate-500 font-medium hidden lg:block leading-none">
              Agentic Multi-Modal Corrective Hybrid RAG
            </p>
          </div>
        </div>

        {/* Active Thread Title if exists */}
        {activeTitle && (
          <div className="hidden xl:flex items-center gap-2 pl-3 border-l border-slate-200 min-w-0">
            <span className="text-xs text-slate-400 font-medium truncate max-w-[240px]">
              {activeTitle}
            </span>
          </div>
        )}
      </div>

      {/* Center: Live Hybrid RAG Engine State Indicator (ChatGPT style) */}
      <div className="flex items-center justify-center">
        {isLoading ? (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200 text-xs font-semibold animate-pulse">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
            <span>Searching &amp; Reranking Knowledge...</span>
          </span>
        ) : (
          <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-slate-50 border border-slate-200 text-xs text-slate-600">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="font-semibold text-slate-800">Hybrid RAG</span>
            <span className="text-slate-300">•</span>
            <span className="text-slate-500">Dense + BM25</span>
            <span className="text-slate-300">•</span>
            <span className="text-indigo-600 font-medium">Self-RAG Grounded</span>
            {docCount > 0 && (
              <>
                <span className="text-slate-300">•</span>
                <span className="text-[11px] text-slate-500">{docCount} docs indexed</span>
              </>
            )}
          </div>
        )}
      </div>

      {/* Right side: New Chat Action */}
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={onResetSession}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-xs hover:shadow transition-all cursor-pointer"
          title="Start a new chat conversation"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Chat</span>
        </button>
      </div>
    </header>
  )
}
