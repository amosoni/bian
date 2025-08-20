import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: true,
    proxy: {
      '/fapi1': { target: 'https://fapi1.binance.com', changeOrigin: true, rewrite: (p) => p.replace(/^\/fapi1/, ''), },
      '/fapi2': { target: 'https://fapi2.binance.com', changeOrigin: true, rewrite: (p) => p.replace(/^\/fapi2/, ''), },
      '/fapi3': { target: 'https://fapi3.binance.com', changeOrigin: true, rewrite: (p) => p.replace(/^\/fapi3/, ''), },
      '/fapi4': { target: 'https://fapi4.binance.com', changeOrigin: true, rewrite: (p) => p.replace(/^\/fapi4/, ''), },
      // Futures testnet (备用)
      '/tfapi': { target: 'https://testnet.binancefuture.com', changeOrigin: true, rewrite: (p) => p.replace(/^\/tfapi/, ''), },
    },
  },
  root: '.',
  build: {
    outDir: 'dist',
  },
  resolve: {
    alias: {
      '@': '/src-frontend'
    }
  }
}) 