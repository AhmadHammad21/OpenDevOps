import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/chat': {
        target: 'http://localhost:8000',
        // Only proxy POST — GET /chat/:sessionId is a React Router route, not an API call
        bypass(req) {
          if (req.method !== 'POST') return req.url;
        },
      },
      '/sessions': 'http://localhost:8000',
      '/stats': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
