import React from 'react'
import { Sparkles, Plus } from 'lucide-react'

interface UserHeaderProps {
  onResetSession: () => void
}

export const UserHeader: React.FC<UserHeaderProps> = ({ onResetSession }) => {
  return (
    <header className="h-16 border-b border-slate-200 bg-white/95 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30 select-none shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
      {/* Brand & Main Project Title */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center text-white shadow-sm">
          <Sparkles className="w-4 h-4" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-extrabold text-base text-slate-900 tracking-tight">
              AMCH-RAG
            </h1>
            <span className="text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
              Personal Assistant
            </span>
            <span className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Online
            </span>
          </div>
          <p className="text-[11px] text-slate-500 font-medium hidden sm:block">
            Agentic Multi-Modal Corrective Hybrid RAG
          </p>
        </div>
      </div>

      {/* Right Action */}
      <button
        onClick={onResetSession}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold border border-slate-200 shadow-xs hover:border-slate-300 transition-all cursor-pointer"
        title="Start a new chat thread"
      >
        <Plus className="w-3.5 h-3.5 text-indigo-600" />
        <span>New Chat</span>
      </button>
    </header>
  )
}
