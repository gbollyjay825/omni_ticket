from datetime import timedelta

from app.models.domain import SlaState, utc_now


class SlaService:
    def refresh(self, sla: SlaState) -> SlaState:
        now = utc_now()
        if now >= sla.first_response_due_at or now >= sla.resolution_due_at:
            sla.risk = "breached"
            sla.breached = True
        elif sla.first_response_due_at - now <= timedelta(minutes=30):
            sla.risk = "at_risk"
            sla.breached = False
        else:
            sla.risk = "on_track"
            sla.breached = False
        return sla


sla_service = SlaService()
