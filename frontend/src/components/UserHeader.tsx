import React from 'react'
import { Sparkles, Plus } from 'lucide-react'

interface UserHeaderProps {
  onResetSession: () => void
}

export const UserHeader: React.FC<UserHeaderProps> = ({ onResetSession }) => {
  return (
    <header className="h-14 border-b border-slate-800 bg-[#090d16]/95 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30 select-none">
      {/* Brand & Title */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm">
          <Sparkles className="w-4 h-4" />
        </div>
        <div>
          <span className="font-semibold text-sm tracking-tight text-white">
            Enterprise Knowledge Assistant
          </span>
        </div>
      </div>

      {/* Right Action: Clean New Thread */}
      <div className="flex items-center gap-2">
        <button
          onClick={onResetSession}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-800 hover:border-slate-700 text-xs font-medium transition-colors"
          title="Start a new clean chat thread"
        >
          <Plus className="w-3.5 h-3.5 text-blue-400" />
          <span>New Chat</span>
        </button>
      </div>
    </header>
  )
}
