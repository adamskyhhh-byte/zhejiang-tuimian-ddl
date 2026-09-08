// Adapted from CS-BAOYAN/CS-BAOYAN-DDL (MIT).
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

export default defineConfig({
  base: process.env.VITE_BASE_PATH || '/',
  plugins: [tailwindcss(), svelte()],
  resolve: { alias: { $lib: path.resolve('src/lib'), $components: path.resolve('src/components') } },
  build: { target: 'es2022', sourcemap: false },
  server: { port: 5180, strictPort: false },
});
