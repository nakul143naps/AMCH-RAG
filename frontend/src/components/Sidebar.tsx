import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FileText,
  UploadCloud,
  Globe,
  Trash2,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  BookOpen,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react'
import type { DocumentItem } from '../types'

interface SidebarProps {
  documents: DocumentItem[]
  onUploadFile: (file: File) => Promise<void>
  onIngestUrl: (url: string) => Promise<void>
  onDeleteDocument: (docId: string) => Promise<void>
  onRefresh: () => Promise<void>
  isOpen: boolean
  onClose: () => void
}

export const Sidebar: React.FC<SidebarProps> = ({
  documents,
  onUploadFile,
  onIngestUrl,
  onDeleteDocument,
  onRefresh,
  isOpen,
  onClose,
}) => {
  const [urlInput, setUrlInput] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [isUrlIngesting, setIsUrlIngesting] = useState(false)
  const [expandedDoc, setExpandedDoc] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [toastMsg, setToastMsg] = useState<string | null>(null)

  const showToast = (msg: string) => {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(null), 3500)
  }

  const handleFileDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0]
      setIsUploading(true)
      try {
        await onUploadFile(file)
        showToast(`Ingested ${file.name}`)
      } catch (err: any) {
        showToast(`Upload failed: ${err.message || 'Error'}`)
      } finally {
        setIsUploading(false)
      }
    }
  }

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0]
      setIsUploading(true)
      try {
        await onUploadFile(file)
        showToast(`Ingested ${file.name}`)
      } catch (err: any) {
        showToast(`Upload failed: ${err.message || 'Error'}`)
      } finally {
        setIsUploading(false)
      }
    }
  }

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!urlInput.trim()) return
    setIsUrlIngesting(true)
    try {
      await onIngestUrl(urlInput.trim())
      showToast(`Ingested URL successfully`)
      setUrlInput('')
    } catch (err: any) {
      showToast(`URL ingest failed: ${err.message || 'Error'}`)
    } finally {
      setIsUrlIngesting(false)
    }
  }

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm z-40 md:hidden"
        />
      )}

      <aside
        className={`fixed md:static inset-y-0 left-0 z-40 w-80 lg:w-88 flex flex-col glass-panel border-r border-slate-800/80 transition-transform duration-300 ${
          isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        {/* Toast Alert */}
        <AnimatePresence>
          {toastMsg && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="m-3 p-3 rounded-xl bg-blue-600/90 text-white text-xs font-medium flex items-center gap-2 shadow-lg"
            >
              <CheckCircle2 className="w-4 h-4 text-emerald-300 shrink-0" />
              <span>{toastMsg}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Section 1: Ingestion Zone */}
        <div className="p-4 border-b border-slate-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              <UploadCloud className="w-4 h-4 text-blue-400" />
              <span>Knowledge Hub Ingest</span>
            </div>
            <button
              onClick={onRefresh}
              className="p-1 rounded-md hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
              title="Refresh Catalog"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Drag & Drop Box */}
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleFileDrop}
            className={`relative rounded-xl border-2 border-dashed p-4 text-center transition-all cursor-pointer ${
              dragOver
                ? 'border-blue-500 bg-blue-500/10'
                : 'border-slate-700 hover:border-slate-600 bg-slate-900/40 hover:bg-slate-900/60'
            }`}
          >
            <input
              type="file"
              onChange={handleFileInput}
              disabled={isUploading}
              accept=".pdf,.docx,.txt,.md,.pptx"
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
            />
            <div className="flex flex-col items-center gap-1.5 pointer-events-none">
              <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-400">
                <FileText className="w-4 h-4" />
              </div>
              <p className="text-xs font-medium text-slate-300">
                {isUploading ? 'Chunking & Indexing...' : 'Drop PDF, DOCX, or TXT here'}
              </p>
              <p className="text-[10px] text-slate-500">Auto-embeds into Qdrant & SQLite cache</p>
            </div>
          </div>

          {/* URL Scraper Input */}
          <form onSubmit={handleUrlSubmit} className="flex gap-1.5">
            <div className="relative flex-1">
              <Globe className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="https://example.com/article"
                className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/60"
              />
            </div>
            <button
              type="submit"
              disabled={isUrlIngesting || !urlInput.trim()}
              className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
            >
              {isUrlIngesting ? '...' : 'Add'}
            </button>
          </form>
        </div>

        {/* Section 2: Document Catalog List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
            <div className="flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-purple-400" />
              <span>Active Corpus ({documents.length})</span>
            </div>
          </div>

          {documents.length === 0 ? (
            <div className="py-8 text-center text-slate-500 text-xs">
              <AlertCircle className="w-6 h-6 mx-auto mb-2 opacity-50" />
              No documents stored yet.
            </div>
          ) : (
            documents.map((doc) => {
              const isExpanded = expandedDoc === doc.doc_id
              return (
                <div
                  key={doc.doc_id}
                  className="rounded-xl border border-slate-800/80 bg-slate-900/40 hover:bg-slate-900/70 transition-all overflow-hidden"
                >
                  <div
                    onClick={() => setExpandedDoc(isExpanded ? null : doc.doc_id)}
                    className="p-3 cursor-pointer flex items-start gap-2.5 select-none"
                  >
                    <div className="w-7 h-7 rounded-lg bg-slate-800/80 flex items-center justify-center text-slate-300 shrink-0 mt-0.5">
                      {doc.source_type === 'html' ? (
                        <Globe className="w-3.5 h-3.5 text-cyan-400" />
                      ) : (
                        <FileText className="w-3.5 h-3.5 text-blue-400" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <h4 className="text-xs font-medium text-slate-200 truncate">
                          {doc.source_name}
                        </h4>
                        {isExpanded ? (
                          <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        ) : (
                          <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700/50">
                          {doc.chunk_count} chunks
                        </span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          {doc.access_level}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Expanded Metadata & Summarized Topics */}
                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="px-3 pb-3 border-t border-slate-800/60 pt-2 text-xs space-y-2 bg-slate-950/40"
                      >
                        {doc.topics && (
                          <div>
                            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-0.5">
                              Topics Index:
                            </span>
                            <p className="text-[11px] text-slate-300 leading-relaxed bg-slate-900/60 p-2 rounded-lg border border-slate-800">
                              {doc.topics}
                            </p>
                          </div>
                        )}

                        {doc.summary && (
                          <div>
                            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-0.5">
                              Executive Summary:
                            </span>
                            <p className="text-[11px] text-slate-300 leading-relaxed bg-slate-900/60 p-2 rounded-lg border border-slate-800">
                              {doc.summary}
                            </p>
                          </div>
                        )}

                        <div className="flex justify-end pt-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              onDeleteDocument(doc.doc_id)
                            }}
                            className="flex items-center gap-1 px-2.5 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 text-[11px] font-medium transition-colors"
                          >
                            <Trash2 className="w-3 h-3" />
                            Delete
                          </button>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )
            })
          )}
        </div>

        {/* Section 3: Clean Summary Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/80 text-xs text-slate-400">
          <div className="flex items-center justify-between text-[11px]">
            <span>Active Knowledge Corpus</span>
            <span className="font-mono text-slate-200 font-semibold">{documents.length} files</span>
          </div>
        </div>
      </aside>
    </>
  )
}
