import React from 'react'
import {
  MessageSquare,
  BarChart3,
  Plus,
  BookOpen,
  Sparkles,
} from 'lucide-react'

interface HeaderProps {
  currentView: 'chat' | 'monitor'
  onViewChange: (view: 'chat' | 'monitor') => void
  onResetSession: () => void
  onToggleSidebar: () => void
  isSidebarOpen: boolean
  documentCount: number
}

export const Header: React.FC<HeaderProps> = ({
  currentView,
  onViewChange,
  onResetSession,
  onToggleSidebar,
  isSidebarOpen,
  documentCount,
}) => {
  return (
    <header className="h-14 border-b border-slate-800 bg-[#090d16]/95 backdrop-blur-md px-5 flex items-center justify-between sticky top-0 z-30 select-none">
      {/* Brand & Workspace Title */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white shadow-sm">
          <Sparkles className="w-4 h-4" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm tracking-tight text-white">
              AMCH Intelligence
            </span>
            <span className="text-[10px] font-medium tracking-wide uppercase px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
              Enterprise
            </span>
          </div>
        </div>
      </div>

      {/* Center Segmented View Switcher: Assistant vs System Monitor */}
      <div className="flex items-center p-1 rounded-lg bg-slate-900/90 border border-slate-800">
        <button
          onClick={() => onViewChange('chat')}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
            currentView === 'chat'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>Assistant</span>
        </button>

        <button
          onClick={() => onViewChange('monitor')}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
            currentView === 'monitor'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5" />
          <span>System Monitor</span>
        </button>
      </div>

      {/* Right Controls: Knowledge Library & New Thread */}
      <div className="flex items-center gap-2">
        {currentView === 'chat' && (
          <>
            <button
              onClick={onToggleSidebar}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                isSidebarOpen
                  ? 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                  : 'bg-slate-900/60 hover:bg-slate-850 text-slate-300 border-slate-800 hover:border-slate-700'
              }`}
              title="Knowledge base documents & ingestion"
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Knowledge Library</span>
              {documentCount > 0 && (
                <span className="px-1.5 py-0.2 rounded-full bg-slate-800 text-[10px] text-slate-400 font-mono">
                  {documentCount}
                </span>
              )}
            </button>

            <button
              onClick={onResetSession}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium shadow-sm transition-all"
              title="Start a new clean chat thread"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New Thread</span>
            </button>
          </>
        )}
      </div>
    </header>
  )
}
