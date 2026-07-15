import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'

const OmniWorkspace = lazy(() => import('../OmniApp'))
const PortalHelpCenter = lazy(() => import('../features/portal/PortalHelpCenter'))
const WidgetMessenger = lazy(() => import('../features/widget/WidgetMessenger'))

function WorkspaceLoadingState() {
  return <main className="workspace-loading" aria-label="Loading Omni workspace" aria-busy="true" />
}

export function OmniRoutes() {
  const screen = new URLSearchParams(window.location.search).get('screen')
  const routedExperience =
    screen === 'portal' ? <PortalHelpCenter /> : screen === 'widget' ? <WidgetMessenger /> : <OmniWorkspace />
  return (
    <Suspense fallback={<WorkspaceLoadingState />}>
      <Routes>
        <Route path="*" element={routedExperience} />
      </Routes>
    </Suspense>
  )
}
