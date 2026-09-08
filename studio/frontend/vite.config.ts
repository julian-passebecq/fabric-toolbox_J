import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react(), {
    name: 'studio-local-boundary',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const port = process.env.STUDIO_UI_PORT || '5173';
        const hosts = [`127.0.0.1:${port}`, `localhost:${port}`];
        const origins = hosts.map(host => `http://${host}`);
        if (!hosts.includes(req.headers.host || '') || (req.headers.origin && !origins.includes(req.headers.origin))) {
          res.statusCode = 403;
          res.end('Untrusted local client host/origin');
          return;
        }
        next();
      });
    },
  }],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('/@fluentui/') || id.includes('/@griffel/')) return 'vendor-fluent';
          if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('/scheduler/')) return 'vendor-react';
          return 'vendor';
        },
      },
    },
  },
  server: {
    host: '127.0.0.1',
    strictPort: true,
    port: Number(process.env.STUDIO_UI_PORT || '5173'),
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${process.env.STUDIO_API_PORT || '8765'}`,
        changeOrigin: true,
        configure(proxy) {
          proxy.on('proxyReq', request => {
            request.removeHeader('x-studio-client');
            request.setHeader('x-studio-client', process.env.STUDIO_CLIENT_TOKEN || '');
          });
        },
      },
    },
  },
});
