import React from 'react'
import {
  MessageSquare,
  Plus,
  Trash2,
  FileText,
  ChevronLeft,
  Sparkles,
} from 'lucide-react'
import type { ChatSession } from '../types'

interface ChatSidebarProps {
  sessions: ChatSession[]
  activeSessionId: string
  onSelectSession: (sessionId: string) => void
  onNewChat: () => void
  onDeleteSession: (sessionId: string) => void
  isOpen: boolean
  onToggle: () => void
  documentCount: number
  onManageDocs?: () => void
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  isOpen,
  onToggle,
  documentCount,
  onManageDocs,
}) => {
  if (!isOpen) return null

  return (
    <aside className="w-64 md:w-72 bg-[#f1f5f9] border-r border-slate-200/90 flex flex-col h-full shrink-0 select-none z-40 transition-all">
      {/* Top Header & New Chat */}
      <div className="p-3 border-b border-slate-200 space-y-2">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold text-xs shadow-xs">
              <Sparkles className="w-3.5 h-3.5" />
            </div>
            <span className="font-bold text-sm text-slate-900 tracking-tight">
              AMCH-RAG
            </span>
          </div>

          <button
            onClick={onToggle}
            className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-500 hover:text-slate-800 transition-colors cursor-pointer"
            title="Collapse sidebar"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        </div>

        {/* New Chat Button (ChatGPT style) */}
        <button
          onClick={onNewChat}
          className="w-full py-2.5 px-3 rounded-xl bg-white hover:bg-slate-50 text-slate-800 text-xs font-semibold flex items-center justify-between border border-slate-200 shadow-xs hover:border-slate-300 transition-all cursor-pointer group"
        >
          <div className="flex items-center gap-2">
            <Plus className="w-4 h-4 text-indigo-600 group-hover:scale-110 transition-transform" />
            <span>New chat</span>
          </div>
          <span className="text-[10px] text-slate-400 font-mono hidden sm:inline">Ctrl + K</span>
        </button>
      </div>

      {/* Recent Chats List */}
      <div className="flex-1 overflow-y-auto px-2 py-3 space-y-1">
        <span className="px-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
          Recent Conversations
        </span>

        {sessions.length === 0 ? (
          <div className="px-3 py-6 text-center text-xs text-slate-400">
            No previous chats yet. Start asking questions!
          </div>
        ) : (
          sessions.map((sess) => {
            const isActive = sess.id === activeSessionId
            return (
              <div
                key={sess.id}
                onClick={() => onSelectSession(sess.id)}
                className={`group flex items-center justify-between px-2.5 py-2 rounded-xl text-xs font-medium cursor-pointer transition-all ${
                  isActive
                    ? 'bg-white text-slate-900 shadow-xs border border-slate-200'
                    : 'text-slate-600 hover:bg-slate-200/70 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-indigo-600' : 'text-slate-400'}`} />
                  <span className="truncate">{sess.title || 'Untitled conversation'}</span>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onDeleteSession(sess.id)
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-rose-50 text-slate-400 hover:text-rose-600 transition-all"
                  title="Delete chat"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            )
          })
        )}
      </div>

      {/* Bottom Knowledge Info with Remove / Manage Option */}
      <div className="p-3 border-t border-slate-200 bg-white/70">
        <button
          onClick={onManageDocs}
          className="w-full p-2.5 rounded-xl bg-slate-50 hover:bg-indigo-50/60 border border-slate-200 hover:border-indigo-200 flex items-center justify-between text-xs transition-all cursor-pointer group text-left"
          title="Click to view and remove indexed documents"
        >
          <div className="flex items-center gap-2 text-slate-700 group-hover:text-indigo-700">
            <FileText className="w-3.5 h-3.5 text-indigo-600" />
            <span className="font-medium">Knowledge Corpus</span>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-indigo-50 group-hover:bg-indigo-100 text-indigo-700 text-[10px] font-bold transition-colors">
            {documentCount} docs &bull; Manage
          </span>
        </button>
      </div>
    </aside>
  )
}
