import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/query': 'http://localhost:8000',
      '/documents': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/metrics': 'http://localhost:8000',
      '/feedback': 'http://localhost:8000',
      '/ingest': 'http://localhost:8000',
      '/admin-api': 'http://localhost:8000',
      '/qdrant-api': {
        target: 'http://localhost:6333',
        rewrite: (path: string) => path.replace(/^\/qdrant-api/, ''),
      },
    },
  },
})
