import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development, the Vite server forwards /api to the FastAPI backend,
// so the browser talks to a single origin (same as the Docker/nginx setup).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': process.env.API_URL ?? 'http://localhost:8000',
    },
  },
})
