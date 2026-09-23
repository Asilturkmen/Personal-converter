import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // CORS yok: /api istekleri backend'e aktarılır, yollar sunucudakiyle aynı kalır.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
});
