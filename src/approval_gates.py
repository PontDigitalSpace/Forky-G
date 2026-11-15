"""Approval gates — which phases pause for a human. EDIT True/False here.

New monthly cycle (Guillermo, 2026-11-14): the client ALREADY has a brand
document, so Phase 1 (brand identity) is NEVER run again. The cycle always
loops like this:

  Análisis (last campaign's data) → Estrategia + Ideas → Plan de contenidos
  → Scripts → Creación → Programación y publicación → Análisis de fin de mes
  → (next month) Estrategia…

- Plan de contenidos: the main idea of each post, in order, which goal it
  targets and the logic/numbers that say it will help reach that goal.
- Scripts: the full copy + script of EVERY piece in the plan. Nothing is
  created before the scripts are approved.

A gated phase (True) makes the runner:
  produce the phase's artifact → report 'awaiting_approval' → PAUSE
  → a human clicks Approve/Reject in the platform dashboard → resume/stop.

Per-client overrides go in CLIENT_GATES (only list the phases that differ).
The brand designer (brand_designer.py, 3 proposals → client picks) still
exists, but only for NEW clients without a brand; it is not part of this cycle.
"""

# The 7 steps of the monthly cycle, in order.
PHASES = [
    "previous_analysis",  # 1. Análisis — data from the previous campaign/month
    "content_strategy",   # 2. Estrategia + ideas
    "content_plan",       # 3. Plan de contenidos (ideas, order, goal, logic)
    "scripts",            # 4. Scripts — copy + guion of every piece
    "production",         # 5. Creación de contenido (run_cycle)
    "publishing",         # 6. Programación y publicación
    "monthly_report",     # 7. Análisis de fin de mes → feeds next strategy
]

# Human-readable names (Spanish, as they appear in ClickUp subtasks).
PHASE_LABELS = {
    "previous_analysis": "1 · Análisis — datos de la campaña anterior",
    "content_strategy":  "2 · Estrategia + Ideas",
    "content_plan":      "3 · Plan de contenidos",
    "scripts":           "4 · Scripts — copy y guion de cada contenido",
    "production":        "5 · Creación de contenido",
    "publishing":        "6 · Programación y publicación",
    "monthly_report":    "7 · Análisis de fin de mes",
}

DEFAULT_GATES = {
    "previous_analysis": False,
    "content_strategy":  False,
    "content_plan":      True,   # approve the plan before writing scripts
    "scripts":           True,   # approve scripts before creating anything
    "production":        False,
    "publishing":        False,  # flip True to review before posting
    "monthly_report":    False,
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
