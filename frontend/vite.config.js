import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icons/apple-touch-icon.png'],
      manifest: {
        name: 'NoB — Neighbourhoods of Bangalore',
        short_name: 'NoB',
        description: 'Self-guided audio walking tours of Bangalore neighbourhoods.',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#F4F0EA',
        theme_color: '#2E2520',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        navigateFallback: '/index.html',
        // The API is never cached by the service worker: purchases, sessions and signed audio URLs must always be live.
        // Walk audio is stored separately by the app (Cache API "nob-audio-v1").
        runtimeCaching: [
          { urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/i, handler: 'StaleWhileRevalidate', options: { cacheName: 'nob-fonts', expiration: { maxEntries: 20 } } },
          { urlPattern: /^https:\/\/tile\.openstreetmap\.org\/.*/i, handler: 'CacheFirst', options: { cacheName: 'nob-map-tiles', expiration: { maxEntries: 300, maxAgeSeconds: 7 * 24 * 3600 }, cacheableResponse: { statuses: [0, 200] } } },
          { urlPattern: /^https:\/\/upload\.wikimedia\.org\/.*/i, handler: 'CacheFirst', options: { cacheName: 'nob-photos', expiration: { maxEntries: 60, maxAgeSeconds: 30 * 24 * 3600 }, cacheableResponse: { statuses: [0, 200] } } },
        ],
      },
    }),
  ],
})
