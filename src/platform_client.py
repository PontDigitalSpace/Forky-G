"""Brain Platform client — live run tracking + approval gates.

Small HTTP client for the platform's agent-run API (brain.pont-digital.ca).
Every phase transition of a Forky-G run is report()ed here so the team sees
"which phase is each agent in" live, and gated phases pause until a human
clicks Approve/Reject in the dashboard.

Env (GitHub secrets / .env):
  BRAIN_PLATFORM_URL   default https://brain.pont-digital.ca
  FORKY_AGENT_KEY      the platform's AGENT_KEY_FORKY_G value

Degrades gracefully: if the key is missing or the platform is unreachable,
runs proceed WITHOUT live tracking (a warning is printed) — the platform is
an observer, never a hard dependency for producing content. The one
exception is a gated phase, which by definition needs the platform to
receive the approval; see PhaseRunner for how that is handled.
"""
from __future__ import annotations
import os
import time
import urllib.parse

import requests

BRAIN = "Forky-G"  # brain name in the platform (must match AGENT_KEY_FORKY_G)


def _base_url() -> str:
    return os.environ.get("BRAIN_PLATFORM_URL", "https://brain.pont-digital.ca").rstrip("/")


def _agent_base() -> str:
    return f"{_base_url()}/api/agent/{urllib.parse.quote(BRAIN)}"


def _headers() -> dict:
    return {"X-Agent-Key": os.environ.get("FORKY_AGENT_KEY", "")}


def is_configured() -> bool:
    return bool(os.environ.get("FORKY_AGENT_KEY", ""))


class PlatformRun:
    """One tracked run. All network errors are caught and printed — tracking
    must never crash the production cycle."""

    def __init__(self, run_id: str | None = None):
        self.run_id = run_id
        self.enabled = is_configured()
        if not self.enabled:
            print("  ⚠️  FORKY_AGENT_KEY not set — running WITHOUT live platform tracking")

    # -- lifecycle ------------------------------------------------------------

    def start(self, client: str, label: str, phases: list[str],
              gates: list[str]) -> str | None:
        if not self.enabled:
            return None
        try:
            r = requests.post(f"{_agent_base()}/runs", headers=_headers(), json={
                "run_id": self.run_id, "client": client, "label": label,
                "phases": phases, "gates": gates,
            }, timeout=15)
            r.raise_for_status()
            self.run_id = r.json()["run_id"]
            print(f"  📡 Run registered on platform: {self.run_id}")
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠️  Platform unreachable ({e}) — continuing untracked")
            self.enabled = False
        return self.run_id

    def report(self, phase: str, index: int, status: str,
               artifact_ref: str = "", artifact_content: str = "",
               error: str = "") -> None:
        """The report() hook — one call per phase transition.

        artifact_content = the deliverable ITSELF (markdown): the team reviews
        and approves IN the platform, without leaving to ClickUp/Drive."""
        if not (self.enabled and self.run_id):
            return
        try:
            requests.post(
                f"{_agent_base()}/runs/{self.run_id}/phase", headers=_headers(),
                json={"phase": phase, "phase_index": index, "status": status,
                      "artifact_ref": artifact_ref,
                      "artifact_content": artifact_content[:60000],
                      "error": error},
                timeout=20,
            ).raise_for_status()
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠️  report({phase}, {status}) failed: {e}")

    def fetch(self) -> dict | None:
        """Current run row from the platform (used by --resume)."""
        if not (self.enabled and self.run_id):
            return None
        try:
            r = requests.get(f"{_base_url()}/api/agent/{urllib.parse.quote(BRAIN)}"
                             f"/runs/{self.run_id}/decision",
                             headers=_headers(), timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception:  # noqa: BLE001
            return None

    # -- approval gate --------------------------------------------------------

    def wait_for_approval(self, phase: str, poll_seconds: int = 30,
                          timeout_minutes: int = 55) -> str:
        """Block until a human decides. Returns 'approved' | 'rejected' |
        'timeout'. On timeout the run stays awaiting_approval on the platform
        and can be finished later with --resume (state lives server-side)."""
        if not (self.enabled and self.run_id):
            # No platform = no way to receive the decision. Fail safe: treat
            # the gate as approved ONLY if explicitly allowed via env.
            if os.environ.get("FORKY_GATES_AUTO_APPROVE", "") == "1":
                print(f"  ⚠️  Gate '{phase}': auto-approved (FORKY_GATES_AUTO_APPROVE=1)")
                return "approved"
            print(f"  ⛔ Gate '{phase}': platform not configured and auto-approve "
                  f"off — stopping here.")
            return "timeout"
        deadline = time.monotonic() + timeout_minutes * 60
        print(f"  ⏸️  Awaiting approval for '{phase}' "
              f"(poll {poll_seconds}s, timeout {timeout_minutes}m)…")
        while time.monotonic() < deadline:
            d = self.fetch()
            decision = (d or {}).get("decision", "")
            if decision in ("approved", "rejected"):
                who = (d or {}).get("decided_by", "?")
                print(f"  {'✅' if decision == 'approved' else '🚫'} "
                      f"'{phase}' {decision} by {who}")
                return decision
            time.sleep(poll_seconds)
        print(f"  ⏳ Approval timeout for '{phase}' — run stays paused on the "
              f"platform; resume later with --resume {self.run_id}")
        return "timeout"
