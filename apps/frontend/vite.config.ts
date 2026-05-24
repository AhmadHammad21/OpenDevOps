import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/chat': {
        target: 'http://localhost:8000',
        // Only proxy POST and DELETE — GET /chat/:sessionId is a React Router route
        bypass(req) {
          if (req.method === 'GET') return req.url;
        },
      },
      '/sessions':        'http://localhost:8000',
      '/stats':           'http://localhost:8000',
      '/auth':            'http://localhost:8000',
      '/api/users':       'http://localhost:8000',
      '/api/settings':    'http://localhost:8000',
      '/api/history':      'http://localhost:8000',
      '/debug':           'http://localhost:8000',
      '/api/monitoring':     'http://localhost:8000',
      '/api/init':           'http://localhost:8000',
      '/api/integrations':   'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
