import { createRoot } from 'react-dom/client'
import './styles.css'
import App from './App.jsx'
createRoot(document.getElementById('root')).render(<App />)

// Offline shell + installable app. Production builds only, so local development is never served from a stale cache.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  import('virtual:pwa-register').then(m => m.registerSW({ immediate: true }))
}
