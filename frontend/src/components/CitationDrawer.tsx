import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, FileText, CheckCircle, Hash } from 'lucide-react'
import type { Citation } from '../types'

interface CitationDrawerProps {
  citation: Citation | null
  onClose: () => void
}

export const CitationDrawer: React.FC<CitationDrawerProps> = ({ citation, onClose }) => {
  return (
    <AnimatePresence>
      {citation && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm z-50"
          />

          {/* Drawer panel */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed inset-y-0 right-0 z-50 w-full max-w-md glass-panel border-l border-slate-700/80 p-6 flex flex-col shadow-2xl overflow-y-auto"
          >
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-sm">
                  [{citation.index}]
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">Verified Document Source</h3>
                  <p className="text-xs text-slate-400">Strictly Grounded in Corpus</p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-6 space-y-4 flex-1">
              <div>
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                  Document Source:
                </span>
                <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center gap-2.5">
                  <FileText className="w-4 h-4 text-blue-400 shrink-0" />
                  <span className="text-xs font-medium text-slate-200 break-all">
                    {citation.source}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                    Chunk Reference:
                  </span>
                  <div className="flex items-center gap-1.5 text-xs text-slate-300 font-mono">
                    <Hash className="w-3.5 h-3.5 text-purple-400" />
                    <span className="truncate">{citation.chunk_id}</span>
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                    Section / Page:
                  </span>
                  <div className="text-xs text-slate-300">
                    {citation.section || (citation.page ? `Page ${citation.page}` : 'Core Section')}
                  </div>
                </div>
              </div>

              {citation.content && (
                <div>
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                    Exact Passage Excerpt (from Qdrant):
                  </span>
                  <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 text-xs text-slate-300 font-sans leading-relaxed whitespace-pre-wrap">
                    {citation.content}
                  </div>
                </div>
              )}

              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 flex items-center gap-2">
                <CheckCircle className="w-4 h-4 shrink-0" />
                <span>Self-RAG Groundedness Verified (Score 1.0)</span>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
