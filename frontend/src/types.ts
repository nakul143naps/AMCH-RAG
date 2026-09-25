export interface Citation {
  index: number
  source: string
  chunk_id: string
  page?: number
  section?: string
  content?: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  citations?: Citation[]
  corrections?: string[]
  trace_id?: string
  provider_used?: string
  route?: string
  latency?: number
  isStreaming?: boolean
}

export interface DocumentItem {
  doc_id: string
  source_name: string
  source_type: string
  access_level: string
  chunk_count: number
  created_at?: string
  summary?: string
  topics?: string
}

export interface SystemHealth {
  status: string
  qdrant: boolean
  cache: {
    backend: string
    status: string
    path: string
  }
  providers: {
    gemini: boolean
    groq: boolean
    openrouter: boolean
  }
}
