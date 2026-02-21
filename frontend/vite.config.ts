import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/__tests__/setup.ts',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    css: false,
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
