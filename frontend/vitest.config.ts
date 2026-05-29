import { defineConfig, type UserConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  // Cast works around a vite version skew: @vitejs/plugin-react resolves vite's
  // Plugin type from the top-level install, while vitest/config expects the
  // Plugin type from its own nested vite. Runtime is unaffected.
  plugins: [react()] as UserConfig['plugins'],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/__tests__/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
    },
  },
});
