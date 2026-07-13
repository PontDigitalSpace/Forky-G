"""Approval gates — which phases pause for a human. EDIT True/False here.

This is the "simple way to program which steps need approval" (owner request,
jul 2026). Defaults = the SAME phases that require approval today by manual
convention (CLAUDE.md): pick a brand identity, approve the monthly plan.

A gated phase (True) makes the runner:
  produce the phase's artifact → report 'awaiting_approval' → PAUSE
  → a human clicks Approve/Reject in the platform dashboard → resume/stop.

Per-client overrides go in CLIENT_GATES (only list the phases that differ).

NOTE: the "no AI images when real footage exists" rule is enforced INSIDE the
production phase (existing pipeline rule), not as a runner gate.
"""

# The 6 phases of the Forky-G cycle, in order (CLAUDE.md «El ciclo»).
PHASES = [
    "brand_identity",    # 1. Documento de Marca (3 propuestas → cliente elige)
    "content_strategy",  # 2. Estrategia + ideas
    "monthly_plan",      # 3. Plan de Contenido Mensual
    "production",        # 4. Producción de contenido (run_cycle)
    "publishing",        # 5. Publicación/agendado en Metricool
    "monthly_report",    # 6. Reporte mensual + análisis
]

DEFAULT_GATES = {
    "brand_identity":  True,   # human picks 1 of 3 proposals (today's gate)
    "content_strategy": False,
    "monthly_plan":    True,   # approve plan before producing (today's gate)
    "production":      False,
    "publishing":      False,  # auto-schedule; flip True to review before posting
    "monthly_report":  False,
}

# Per-client overrides, e.g. {"la_medusa": {"publishing": True}}
CLIENT_GATES: dict[str, dict[str, bool]] = {}


def gates_for(client: str) -> dict[str, bool]:
    """Effective gate map for a client (defaults + overrides)."""
    g = dict(DEFAULT_GATES)
    g.update(CLIENT_GATES.get(client, {}))
    return g


def gated_phases(client: str) -> list[str]:
    """Ordered list of phase names that pause for approval for this client."""
    g = gates_for(client)
    return [p for p in PHASES if g.get(p, False)]
