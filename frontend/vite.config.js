import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          const normalized = id.replace(/\\/g, '/');

          if (
            normalized.includes('/node_modules/react/') ||
            normalized.includes('/node_modules/react-dom/') ||
            normalized.includes('/node_modules/scheduler/')
          ) {
            return 'vendor-react';
          }

          if (
            normalized.includes('/node_modules/react-router-dom/') ||
            normalized.includes('/node_modules/react-router/') ||
            normalized.includes('/node_modules/@remix-run/router/')
          ) {
            return 'vendor-router';
          }

          if (normalized.includes('/node_modules/ag-grid-react/')) {
            return 'vendor-ag-grid-react';
          }

          if (normalized.includes('/node_modules/ag-stack/')) {
            return 'vendor-ag-stack';
          }

          if (normalized.includes('/node_modules/ag-grid-community/')) {
            return 'vendor-ag-grid';
          }

          return 'vendor';
        },
      },
    },
  },
});
