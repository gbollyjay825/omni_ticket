import { Bot } from 'lucide-react'

import type { BackendSession } from '../../backend'
import { AiStudioConsole } from '../omnichat/AiStudioConsole'
import '../parity-workspaces.css'

interface AiAgentsWorkspaceProps {
  session: BackendSession | null
  canManage: boolean
  onOpenCredentials: () => void
}

export function AiAgentsWorkspace({
  session,
  canManage,
  onOpenCredentials,
}: AiAgentsWorkspaceProps) {
  return (
    <section className="connected-workspace" aria-label="AI Agents and Chatbots workspace">
      <header className="connected-workspace-heading">
        <span className="connected-workspace-icon"><Bot size={20} /></span>
        <span>
          <strong>AI Agents &amp; Chatbots</strong>
          <small>Build and deploy AI support across active customer channels</small>
        </span>
      </header>
      <div className="connected-workspace-body">
        <AiStudioConsole
          session={session}
          canManage={canManage}
          onOpenCredentials={onOpenCredentials}
        />
      </div>
    </section>
  )
}
