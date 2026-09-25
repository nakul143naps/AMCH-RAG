import React from 'react'
import { Sparkles, Plus } from 'lucide-react'

interface UserHeaderProps {
  onResetSession: () => void
}

export const UserHeader: React.FC<UserHeaderProps> = ({ onResetSession }) => {
  return (
    <header className="h-14 border-b border-slate-200 bg-white/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30 select-none shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
      {/* Brand & Persona */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-violet-600 flex items-center justify-center text-white shadow-sm">
          <Sparkles className="w-4 h-4" />
        </div>
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-slate-900 tracking-tight">
            Aura
          </span>
          <span className="text-[11px] text-slate-500 font-normal">
            Personal Knowledge Assistant
          </span>
          <span className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200 ml-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Ready
          </span>
        </div>
      </div>

      {/* Right Action */}
      <button
        onClick={onResetSession}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium border border-slate-200 shadow-sm hover:border-slate-300 transition-all"
        title="Start a new chat"
      >
        <Plus className="w-3.5 h-3.5 text-indigo-600" />
        <span>New Chat</span>
      </button>
    </header>
  )
}
