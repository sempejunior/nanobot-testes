import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

const isDev = process.env.NODE_ENV !== 'production'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: isDev ? '/' : '/static/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': process.env.VITE_API_URL || 'http://127.0.0.1:18790',
      '/ws': { target: process.env.VITE_API_URL || 'ws://127.0.0.1:18790', ws: true },
    },
  },
  build: {
    outDir: 'static',
    emptyOutDir: true,
  },
})
