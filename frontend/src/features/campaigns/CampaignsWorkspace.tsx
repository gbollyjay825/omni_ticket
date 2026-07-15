import { BarChart3, Megaphone, MessageSquareText } from 'lucide-react'

import type { BackendSession } from '../../backend'
import { CampaignConsole } from '../omnichat/CampaignConsole'
import '../parity-workspaces.css'

interface CampaignsWorkspaceProps {
  session: BackendSession | null
  canManage: boolean
  onOpenSettings: () => void
}

export function CampaignsWorkspace({
  session,
  canManage,
  onOpenSettings,
}: CampaignsWorkspaceProps) {
  return (
    <section className="connected-workspace connected-workspace-with-rail" aria-label="Proactive campaigns workspace">
      <aside aria-label="Campaign views">
        <span className="active" role="img" aria-label="Campaigns"><Megaphone size={17} /></span>
        <span role="img" aria-label="Campaign delivery status"><BarChart3 size={17} /></span>
        <span role="img" aria-label="Message templates"><MessageSquareText size={17} /></span>
      </aside>
      <div className="connected-workspace-main">
        <header className="connected-workspace-heading">
          <span className="connected-workspace-icon campaign"><Megaphone size={20} /></span>
          <span>
            <strong>WhatsApp Proactive Campaigns</strong>
            <small>Audiences, approved templates, delivery status, and provider readiness</small>
          </span>
        </header>
        <div className="connected-workspace-body">
          <CampaignConsole session={session} canManage={canManage} onOpenSettings={onOpenSettings} />
        </div>
      </div>
    </section>
  )
}
