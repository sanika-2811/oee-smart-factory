import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The backend serves REST at the root and the live feed at /ws/live. In dev the SPA talks to it through
// the "/api" prefix (proxied here); in Docker nginx does the same (deploy/nginx.conf).
const target = process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': { target, changeOrigin: true, ws: true, rewrite: (p) => p.replace(/^\/api/, '') },
    },
  },
  preview: { port: 5173 },
  test: { environment: 'node', include: ['tests/**/*.test.ts'] },
})
