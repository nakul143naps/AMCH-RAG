import React, { useState, useEffect, useRef } from 'react'
import {
  X,
  FileText,
  Trash2,
  Upload,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Database,
  Globe,
} from 'lucide-react'
import type { DocumentItem } from '../types'

interface DocumentManagerModalProps {
  isOpen: boolean
  onClose: () => void
  onDocumentsChanged: () => void
}

export const DocumentManagerModal: React.FC<DocumentManagerModalProps> = ({
  isOpen,
  onClose,
  onDocumentsChanged,
}) => {
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [uploadStatus, setUploadStatus] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const fetchDocuments = async () => {
    setIsLoading(true)
    try {
      const res = await fetch('/documents')
      if (res.ok) {
        const data = await res.json()
        setDocuments(data.documents || [])
      }
    } catch (err) {
      console.error('Failed to load documents:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchDocuments()
    }
  }, [isOpen])

  const handleDelete = async (docId: string, docName: string) => {
    if (!confirm(`Are you sure you want to remove "${docName}" from your knowledge corpus?`)) {
      return
    }

    setDeletingId(docId)
    try {
      const res = await fetch(`/documents/${docId}`, {
        method: 'DELETE',
      })
      if (!res.ok) throw new Error(`Delete failed with status ${res.status}`)

      // Remove from local list immediately
      setDocuments((prev) => prev.filter((d) => d.doc_id !== docId))
      onDocumentsChanged()
    } catch (err: any) {
      alert(`Could not delete document: ${err.message}`)
    } finally {
      setDeletingId(null)
    }
  }

  const handleFileUpload = async (file: File) => {
    setIsUploading(true)
    setUploadStatus(`Uploading "${file.name}"...`)
    const formData = new FormData()
    formData.append('file', file)
    formData.append('access_level', 'default')

    try {
      const res = await fetch('/ingest', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) throw new Error(`Upload failed with status ${res.status}`)
      const data = await res.json()
      const jobId = data.job_id

      setUploadStatus(`Indexing and generating vector embeddings...`)

      if (jobId) {
        let attempts = 0
        const poll = setInterval(async () => {
          attempts++
          try {
            const statusRes = await fetch(`/ingest/${jobId}`)
            if (statusRes.ok) {
              const statusData = await statusRes.json()
              if (statusData.status === 'completed') {
                clearInterval(poll)
                setIsUploading(false)
                setUploadStatus(`"${file.name}" successfully indexed!`)
                fetchDocuments()
                onDocumentsChanged()
                setTimeout(() => setUploadStatus(null), 4000)
              } else if (statusData.status === 'failed') {
                clearInterval(poll)
                setIsUploading(false)
                setUploadStatus(`Failed: ${statusData.error || 'Ingest error'}`)
                setTimeout(() => setUploadStatus(null), 5000)
              }
            }
          } catch {
            // ignore network glitch
          }

          if (attempts > 30) {
            clearInterval(poll)
            setIsUploading(false)
            setUploadStatus('Uploaded. Processing completed in background.')
            fetchDocuments()
            onDocumentsChanged()
            setTimeout(() => setUploadStatus(null), 4000)
          }
        }, 1500)
      } else {
        setIsUploading(false)
        setUploadStatus('Uploaded successfully.')
        fetchDocuments()
        onDocumentsChanged()
      }
    } catch (err: any) {
      setIsUploading(false)
      setUploadStatus(`Upload error: ${err.message}`)
      setTimeout(() => setUploadStatus(null), 5000)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-fadeIn">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-xl max-h-[85vh] flex flex-col overflow-hidden">
        {/* Modal Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
              <Database className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 tracking-tight">
                Knowledge Documents
              </h2>
              <p className="text-xs text-slate-500">
                Manage files indexed in your personal AMCH-RAG knowledge corpus
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-xl hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors cursor-pointer"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Upload Status Banner */}
        {uploadStatus && (
          <div className="px-5 py-2.5 bg-indigo-50 border-b border-indigo-100 text-xs text-indigo-700 flex items-center gap-2">
            {isUploading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-600" />
            ) : uploadStatus.includes('error') || uploadStatus.includes('Failed') ? (
              <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
            ) : (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            )}
            <span className="font-medium">{uploadStatus}</span>
          </div>
        )}

        {/* Documents List */}
        <div className="flex-1 overflow-y-auto p-5 space-y-2">
          {isLoading ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-400 text-xs">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-600 mb-2" />
              <span>Loading indexed knowledge documents...</span>
            </div>
          ) : documents.length === 0 ? (
            <div className="py-12 text-center text-slate-400 space-y-2">
              <FileText className="w-8 h-8 mx-auto text-slate-300" />
              <p className="text-xs font-medium text-slate-600">No documents indexed yet</p>
              <p className="text-[11px] text-slate-400 max-w-xs mx-auto">
                Upload PDFs, notes, or articles below to allow AMCH-RAG to answer questions from them.
              </p>
            </div>
          ) : (
            documents.map((doc) => {
              const isDeleting = deletingId === doc.doc_id
              const isUrl = doc.source_name.startsWith('http://') || doc.source_name.startsWith('https://')

              return (
                <div
                  key={doc.doc_id}
                  className="flex items-center justify-between p-3 rounded-xl bg-slate-50 hover:bg-slate-100/70 border border-slate-200/80 transition-all group"
                >
                  <div className="flex items-center gap-3 min-w-0 mr-2">
                    <div className="w-8 h-8 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-slate-600 shrink-0 shadow-xs">
                      {isUrl ? (
                        <Globe className="w-4 h-4 text-sky-600" />
                      ) : (
                        <FileText className="w-4 h-4 text-indigo-600" />
                      )}
                    </div>

                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-800 truncate" title={doc.source_name}>
                        {doc.source_name}
                      </p>
                      <div className="flex items-center gap-2 text-[10px] text-slate-400 mt-0.5">
                        <span className="px-1.5 py-0.2 rounded bg-indigo-50 text-indigo-700 font-medium">
                          {doc.chunk_count} {doc.chunk_count === 1 ? 'chunk' : 'chunks'}
                        </span>
                        <span>&bull;</span>
                        <span className="uppercase">{doc.source_type || 'file'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Remove Button */}
                  <button
                    onClick={() => handleDelete(doc.doc_id, doc.source_name)}
                    disabled={isDeleting}
                    className="p-2 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors disabled:opacity-40 cursor-pointer shrink-0"
                    title="Remove document from knowledge corpus"
                  >
                    {isDeleting ? (
                      <Loader2 className="w-4 h-4 animate-spin text-rose-600" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </div>
              )
            })
          )}
        </div>

        {/* Modal Footer with Upload Action */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between">
          <span className="text-[11px] text-slate-500 font-medium">
            {documents.length} {documents.length === 1 ? 'document' : 'documents'} in corpus
          </span>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-xs hover:shadow transition-all disabled:opacity-50 cursor-pointer"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Add Document</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) handleFileUpload(f)
                e.target.value = ''
              }}
              className="hidden"
              accept=".pdf,.docx,.txt,.md,.csv,.html"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
