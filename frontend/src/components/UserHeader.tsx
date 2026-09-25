import React from 'react'
import { Sparkles, Plus } from 'lucide-react'

interface UserHeaderProps {
  onResetSession: () => void
}

export const UserHeader: React.FC<UserHeaderProps> = ({ onResetSession }) => {
  return (
    <header className="h-14 border-b border-white/5 bg-[#0f1117]/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30 select-none">
      {/* Brand & Personal Assistant Persona */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-violet-600 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-violet-500/20">
          <Sparkles className="w-4 h-4" />
        </div>
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-white tracking-tight">
            Aura
          </span>
          <span className="text-[11px] text-zinc-400 font-normal">
            Personal Knowledge Assistant
          </span>
          <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20 ml-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Online
          </span>
        </div>
      </div>

      {/* Right Action: Clean New Conversation */}
      <button
        onClick={onResetSession}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-800/80 hover:bg-zinc-700/80 text-zinc-200 text-xs font-medium border border-white/5 transition-all shadow-sm"
        title="Start a fresh conversation"
      >
        <Plus className="w-3.5 h-3.5 text-violet-400" />
        <span>New Chat</span>
      </button>
    </header>
  )
}
