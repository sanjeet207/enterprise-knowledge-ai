import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The built interface is served by FastAPI from /static, so production assets are built there.
// In development the dev server proxies every API call to the running FastAPI server on port 8000.
const api = { target: 'http://127.0.0.1:8000', changeOrigin: false }

export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/' : '/',
  plugins: [react()],
  build: { outDir: '../app/static', emptyOutDir: true },
  server: {
    proxy: {
      '/auth': api, '/chat': api, '/audit': api, '/documents': api,
      '/admin': api, '/research': api, '/me': api, '/health': api,
    },
  },
}))
