import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // CORS yok: /api istekleri backend'e aktarılır, yollar sunucudakiyle aynı kalır.
    // xfwd: istemcinin gerçek adresi X-Forwarded-For ile iletilir; `npm run dev:lan`
    // ile telefondan bağlanıldığında IP sınırları telefon ile bilgisayarı ayırt eder.
    proxy: { '/api': { target: 'http://127.0.0.1:8000', xfwd: true } },
  },
});
