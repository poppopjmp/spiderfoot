import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'https://localhost',
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: 'wss://localhost',
        ws: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: '../spiderfoot/static/react',
    emptyOutDir: true,
    sourcemap: true,
  },
});
