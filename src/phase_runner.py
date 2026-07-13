"""Phase runner — Forky-G's cycle as 6 tracked phases with approval gates.

Turns the monthly cycle (CLAUDE.md «El ciclo») into an orchestrated run the
team can watch live on the platform (brain.pont-digital.ca) and approve at
the gates defined in approval_gates.py.

Semantics per phase:
  - AUTOMATED phase (impl wired, e.g. production → run_cycle): report
    'running' → execute → report result.
  - MANUAL phase (impl None — not yet automated): reported as done with a
    note, UNLESS gated: then the run PAUSES ('awaiting_approval') so a human
    does/reviews that step (e.g. approve the monthly plan in ClickUp) and
    clicks Approve in the dashboard to continue.
  - GATED phase: after the phase's work, the run pauses until Approve/Reject.

State lives on the PLATFORM, so a run interrupted at a gate (e.g. GitHub
Actions timeout) is finished later with:  --resume <run_id>

Usage:
  python phase_runner.py --client la_medusa --month julio_2026
  python phase_runner.py --client la_medusa --month julio_2026 --only 3
  python phase_runner.py --resume ab12cd34ef56 --client la_medusa --month julio_2026
"""
from __future__ import annotations
import argparse
import os
import sys

from approval_gates import PHASES, gated_phases
from platform_client import PlatformRun

POLL_SECONDS = int(os.environ.get("FORKY_GATE_POLL_SECONDS", "30"))
TIMEOUT_MINUTES = int(os.environ.get("FORKY_GATE_TIMEOUT_MINUTES", "55"))


# ---------------------------------------------------------------------------
# Phase implementations. None = manual (not yet automated) — the runner
# reports it and, if gated, pauses for the human to do/review it.
# ---------------------------------------------------------------------------

def _production(client: str, month: str, only_post: int | None,
                use_scriptwriter: bool) -> None:
    from forky_g import run_cycle  # lazy: heavy module
    from platform_client import get_brain_context, observe

    # SELF-LEARNING (read): pull learned rules/experience from the brain and
    # expose them to the generation prompts (script_writer reads this env).
    ctx = get_brain_context(query=f"content production rules {client}")
    if ctx:
        os.environ["FORKY_BRAIN_CONTEXT"] = ctx
        print(f"  🧠 brain context injected ({len(ctx)} chars)")

    run_cycle(client, month, only_post=only_post, use_scriptwriter=use_scriptwriter)

    # SELF-LEARNING (observe): record each produced post's content-DNA AT
    # CREATION TIME (vault rule: never re-watch own videos later) + the run
    # outcome. The platform's hippocampus dedups/filters what sticks.
    import json as _json
    from pathlib import Path as _P
    summary_file = _P("output") / client / month / "cycle_summary.json"
    if summary_file.exists():
        s = _json.loads(summary_file.read_text(encoding="utf-8"))
        items = [{
            "content": (f"[content-DNA] {client}/{month} post produced: "
                        f"hook='{p.get('hook', '')[:80]}' "
                        f"format={p.get('format', '?')} "
                        f"platforms={p.get('platforms', [])} "
                        f"files={len(p.get('files', []))}"),
            "tags": ["content-dna", client, month],
        } for p in (s.get("posts") or [])]
        items.append({
            "content": (f"[run-outcome] {client}/{month}: "
                        f"{s.get('success', 0)}/{s.get('total', 0)} posts ok "
                        f"({'all good' if s.get('success') == s.get('total') else 'some failed — check logs'})"),
            "tags": ["run-outcome", client, month],
        })
        observe(items)


PHASE_IMPLS: dict[str, object] = {
    "brand_identity":  None,  # brand_designer.py exists; one-time per client, manual for now
    "content_strategy": None,
    "monthly_plan":    None,  # plan lives in ClickUp; approval gate covers review
    "production":      _production,
    "publishing":      None,  # metricool scheduling not wired into the runner yet
    "monthly_report":  None,
}

EXIT_PAUSED = 75    # gate timeout: run stays paused server-side, resume later
EXIT_REJECTED = 2


def run_phases(client: str, month: str, run_id: str | None = None,
               only_post: int | None = None, use_scriptwriter: bool = False,
               start_index: int = 1) -> int:
    """Run phases [start_index..6] (1-based). Returns process exit code."""
    gates = set(gated_phases(client))
    run = PlatformRun(run_id)
    if start_index == 1:
        run.start(client=client, label=month, phases=PHASES,
                  gates=[p for p in PHASES if p in gates])
    total = len(PHASES)

    for i, phase in enumerate(PHASES, start=1):
        if i < start_index:
            continue
        impl = PHASE_IMPLS.get(phase)
        print(f"\n{'='*60}\n  ▶️  PHASE {i}/{total} — {phase}"
              f"{' (manual)' if impl is None else ''}{' 🚧 gated' if phase in gates else ''}")
        run.report(phase, i, "running")

        # 1) Do the phase's work (if automated). If the impl returns a string,
        #    that's the phase's ARTIFACT (markdown) — reviewed IN the platform.
        artifact = ""
        if impl is not None:
            try:
                artifact = impl(client, month, only_post, use_scriptwriter) or ""
            except (Exception, SystemExit) as e:  # noqa: BLE001
                print(f"  ❌ Phase '{phase}' failed: {e}")
                run.report(phase, i, "failed", error=str(e))
                return 1
        else:
            print(f"  ℹ️  '{phase}' is not automated yet — "
                  f"{'pausing for the human step' if phase in gates else 'skipping'}")

        # 2) Gate: pause for a human decision before moving on.
        if phase in gates:
            run.report(phase, i, "awaiting_approval",
                       artifact_content=str(artifact))
            decision = run.wait_for_approval(phase, POLL_SECONDS, TIMEOUT_MINUTES)
            if decision == "rejected":
                print(f"  🚫 Run stopped: '{phase}' was rejected.")
                return EXIT_REJECTED
            if decision == "timeout":
                return EXIT_PAUSED
            # approved → fall through to next phase

    run.report(PHASES[-1], total, "done")
    print(f"\n✅ Cycle complete — all {total} phases finished.")
    return 0


def resume(run_id: str, client: str, month: str, only_post: int | None,
           use_scriptwriter: bool) -> int:
    """Continue a paused/interrupted run from the state stored on the platform."""
    run = PlatformRun(run_id)
    state = run.fetch()
    if not state:
        print(f"❌ Cannot fetch run '{run_id}' from the platform.")
        return 1
    status, idx = state.get("status"), int(state.get("phase_index") or 1)
    decision = state.get("decision", "")
    print(f"📡 Resuming run {run_id}: status={status}, phase {idx}/{len(PHASES)}")
    if status in ("done", "rejected"):
        print(f"Nothing to do — run already {status}.")
        return 0
    if status == "awaiting_approval":
        if decision == "rejected":
            return EXIT_REJECTED
        if decision != "approved":
            d = run.wait_for_approval(state.get("current_phase", "?"),
                                      POLL_SECONDS, TIMEOUT_MINUTES)
            if d == "rejected":
                return EXIT_REJECTED
            if d == "timeout":
                return EXIT_PAUSED
        idx += 1  # gate cleared → continue from the NEXT phase
    return run_phases(client, month, run_id=run_id, only_post=only_post,
                      use_scriptwriter=use_scriptwriter, start_index=idx)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Forky-G phase runner (gated cycle)")
    p.add_argument("--client", default="la_medusa")
    p.add_argument("--month", default="julio_2026")
    p.add_argument("--run-id", default=None, help="idempotent run id (CI retries)")
    p.add_argument("--resume", default=None, metavar="RUN_ID",
                   help="continue a paused run from platform state")
    p.add_argument("--only", type=int, default=None, help="single-post test in production")
    p.add_argument("--script", action="store_true", help="use scriptwriter role")
    a = p.parse_args()

    if a.resume:
        code = resume(a.resume, a.client, a.month, a.only, a.script)
    else:
        code = run_phases(a.client, a.month, run_id=a.run_id,
                          only_post=a.only, use_scriptwriter=a.script)
    sys.exit(code)
