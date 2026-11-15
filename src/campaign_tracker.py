"""ClickUp tracking for the monthly campaign: ONE task per month, each phase a SUBTASK.

Rule (Guillermo, 2026-11-14): «Campaña <Mes Año>_<Cliente>» lives in the
client's «Marketing Orgánico» list; every phase of the cycle is a subtask of it.
The runner calls start() once and set_phase() as each phase moves.

Documents are NOT uploaded to ClickUp (free plan, no storage): they go to Drive
as Word and only the link is posted as a comment on the phase subtask.

Needs CLICKUP_API_TOKEN (and optionally CLICKUP_WORKSPACE_ID). Without a token
it logs a warning and does nothing — the cycle still runs.
"""
from __future__ import annotations
import os
import unicodedata

import requests

from approval_gates import PHASE_LABELS, PHASES

API = "https://api.clickup.com/api/v2"
LIST_NAME = os.environ.get("CLICKUP_CAMPAIGN_LIST", "Marketing Orgánico")

# client key (workflow input) → ClickUp folder name. Unknown keys fall back to a
# normalized match on the folder name.
CLIENT_FOLDERS = {
    "pont_digital": "Pont Digital",
    "la_medusa": "La Medusa",
    "scholeia": "Scholeía Inc nueva",
    "revues": "Revues",
    "sound_of_law": "Sound of Law",
    "dintys": "Dinty's",
}

# ClickUp statuses used in the PD workspace.
ST_TODO, ST_DOING, ST_REVIEW, ST_DONE = "sin empezar", "en progreso", "entrega a dirección", "completado"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return "".join(c for c in s.lower() if c.isalnum())


def month_label(month: str) -> str:
    """'diciembre_2026' → 'Diciembre 2026'."""
    parts = (month or "").replace("-", "_").split("_")
    return " ".join(p.capitalize() for p in parts if p)


class CampaignTracker:
    def __init__(self, client: str, month: str):
        self.token = os.environ.get("CLICKUP_API_TOKEN", "")
        self.client, self.month = client, month
        self.parent_id: str | None = None
        self.subtasks: dict[str, str] = {}   # phase key → task id
        self.enabled = bool(self.token)
        if not self.enabled:
            print("  ⚠️ CLICKUP_API_TOKEN not set — the campaign task won't be created in ClickUp.")

    # -- http -----------------------------------------------------------------
    def _h(self) -> dict:
        return {"Authorization": self.token, "Content-Type": "application/json"}

    def _get(self, path: str) -> dict:
        r = requests.get(API + path, headers=self._h(), timeout=30)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        r = requests.post(API + path, headers=self._h(), json=body, timeout=30)
        r.raise_for_status()
        return r.json()

    def _put(self, path: str, body: dict) -> dict:
        r = requests.put(API + path, headers=self._h(), json=body, timeout=30)
        r.raise_for_status()
        return r.json()

    # -- lookup ---------------------------------------------------------------
    def _campaign_list_id(self) -> str:
        team = os.environ.get("CLICKUP_WORKSPACE_ID") or self._get("/team")["teams"][0]["id"]
        want = _norm(CLIENT_FOLDERS.get(self.client, self.client.replace("_", " ")))
        for sp in self._get(f"/team/{team}/space?archived=false")["spaces"]:
            for f in self._get(f"/space/{sp['id']}/folder?archived=false")["folders"]:
                if _norm(f["name"]) == want:
                    for l in f.get("lists", []):
                        if _norm(l["name"]) == _norm(LIST_NAME):
                            self.folder_name = f["name"]
                            return l["id"]
                    raise RuntimeError(f"folder «{f['name']}» has no «{LIST_NAME}» list")
        raise RuntimeError(f"no ClickUp folder for client «{self.client}»")

    # -- public ---------------------------------------------------------------
    def start(self) -> None:
        """Create (or reuse) the month task and its phase subtasks."""
        if not self.enabled:
            return
        try:
            lid = self._campaign_list_id()
            name = f"Campaña {month_label(self.month)}_{self.folder_name}"
            tasks = self._get(f"/list/{lid}/task?include_closed=true&subtasks=true").get("tasks", [])
            parent = next((t for t in tasks if _norm(t["name"]) == _norm(name) and not t.get("parent")), None)
            if parent is None:
                parent = self._post(f"/list/{lid}/task", {
                    "name": name, "status": ST_TODO,
                    "description": ("Campaña orgánica del mes. Cada fase es una subtarea. Ciclo: "
                                    "Análisis → Estrategia → Plan → Scripts → Creación → Publicación "
                                    "→ Análisis. La Fase 1 (marca) no se hace: la marca ya existe."),
                })
                print(f"  🗂  ClickUp: created «{name}»")
            else:
                print(f"  🗂  ClickUp: reusing «{name}»")
            self.parent_id = parent["id"]
            existing = {_norm(t["name"]): t["id"] for t in tasks if t.get("parent") == self.parent_id}
            for key in PHASES:
                label = PHASE_LABELS[key]
                tid = existing.get(_norm(label))
                if tid is None:
                    tid = self._post(f"/list/{lid}/task", {
                        "name": label, "parent": self.parent_id, "status": ST_TODO})["id"]
                self.subtasks[key] = tid
        except Exception as e:  # noqa: BLE001 — tracking must never stop the cycle
            print(f"  ⚠️ ClickUp tracking disabled: {e}")
            self.enabled = False

    def set_phase(self, phase: str, state: str, note: str = "") -> None:
        """state: running | awaiting_approval | done | failed."""
        if not self.enabled or phase not in self.subtasks:
            return
        status = {"running": ST_DOING, "awaiting_approval": ST_REVIEW,
                  "done": ST_DONE, "failed": ST_DOING}.get(state, ST_DOING)
        tid = self.subtasks[phase]
        try:
            self._put(f"/task/{tid}", {"status": status})
            if note:
                self._post(f"/task/{tid}/comment", {"comment_text": f"🤖 Forky G — {note}"})
            if self.parent_id and state == "running":
                self._put(f"/task/{self.parent_id}", {"status": ST_DOING})
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠️ ClickUp status update failed for {phase}: {e}")

    def finish(self) -> None:
        if self.enabled and self.parent_id:
            try:
                self._put(f"/task/{self.parent_id}", {"status": ST_REVIEW})
            except Exception as e:  # noqa: BLE001
                print(f"  ⚠️ ClickUp: could not close the campaign task: {e}")
