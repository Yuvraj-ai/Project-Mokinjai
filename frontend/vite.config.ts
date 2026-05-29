import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
const wsBackendUrl = backendUrl.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/ws': {
        target: wsBackendUrl,
        ws: true,
      },
    },
  },
})
