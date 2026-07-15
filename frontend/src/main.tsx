import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { AppProviders } from './app/AppProviders.tsx'
import { OmniRoutes } from './app/OmniRoutes.tsx'
import { registerServiceWorker } from './pwa.ts'

registerServiceWorker()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProviders>
      <OmniRoutes />
    </AppProviders>
  </StrictMode>,
)
