"""
ClickUp Client — implements Pont Digital's INPUT/OUTPUT storage convention.

See CLAUDE.md → "Cómo Pont Digital usa ClickUp" for the rules this enforces.

INPUT side (what the agent reads):
  - read a task (description + comments)
  - read a ClickUp Doc's pages (for the occasional "info lives in a ClickUp Doc" case)
  - find Drive links inside a task → hand off to drive_downloader for syncing

OUTPUT side (what the agent produces):
  - create a real ClickUp Doc in the Docs area (NEVER as a List in the hierarchy)
  - link that Doc back to a task (via comment + task link) so the team reaches it
    from the task and can give inline feedback on the Doc

Auth: ClickUp personal token (pk_...) in env CLICKUP_API_TOKEN.
Workspace (team) id in env CLICKUP_WORKSPACE_ID — needed for the Docs (v3) API.

NOTE: ClickUp split its API across versions. Tasks/comments are stable on v2;
Docs live on the v3 API. Endpoint shapes below follow ClickUp's published API;
if ClickUp changes them, adjust here only. Defensive parsing mirrors the style of
higgsfield_client.py (tolerate multiple response shapes).
"""
from __future__ import annotations
import os
import requests

API_V2 = "https://api.clickup.com/api/v2"
API_V3 = "https://api.clickup.com/api/v3"

CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
CLICKUP_WORKSPACE_ID = os.environ.get("CLICKUP_WORKSPACE_ID", "")


def _headers() -> dict:
    if not CLICKUP_API_TOKEN:
        raise RuntimeError("CLICKUP_API_TOKEN not set")
    return {"Authorization": CLICKUP_API_TOKEN, "Content-Type": "application/json"}


# ============================ INPUT side ======================================

def get_task(task_id: str) -> dict:
    """Fetch a task (includes description, status, custom fields, attachments)."""
    r = requests.get(f"{API_V2}/task/{task_id}", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def get_folder_lists(folder_id: str) -> list[dict]:
    """All lists inside a client folder (ONBOARDING, ADS, Administrativo, ...)."""
    r = requests.get(f"{API_V2}/folder/{folder_id}/list", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("lists", [])


def get_list_tasks(list_id: str, include_closed: bool = True) -> list[dict]:
    """
    All tasks in a list, INCLUDING subtasks (returned as separate entries with a
    'parent' set). Each task carries its own 'attachments' array.
    """
    params = {
        "include_closed": "true" if include_closed else "false",
        "subtasks": "true",
    }
    r = requests.get(f"{API_V2}/list/{list_id}/task", headers=_headers(),
                     params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("tasks", [])


def get_task_attachments(task: dict) -> list[dict]:
    """
    Pull downloadable attachments off a task object (works for tasks AND subtasks,
    since both expose the same 'attachments' array). Returns
    [{"title", "url", "extension"}].
    """
    out = []
    for a in task.get("attachments", []) or []:
        url = a.get("url") or a.get("url_w_query")
        if url:
            out.append({
                "title": a.get("title") or a.get("name") or "attachment",
                "url": url,
                "extension": a.get("extension", ""),
            })
    return out


def download_attachment(url: str, dest_path: str) -> str:
    """
    Download a ClickUp attachment to dest_path. ClickUp attachment URLs are usually
    directly fetchable; fall back to sending the auth header if access is denied.
    """
    from pathlib import Path
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, stream=True, timeout=60)
    if r.status_code in (401, 403):
        r = requests.get(url, headers={"Authorization": CLICKUP_API_TOKEN},
                         stream=True, timeout=60)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return dest_path


def get_task_comments(task_id: str) -> list[dict]:
    """Fetch a task's comments."""
    r = requests.get(f"{API_V2}/task/{task_id}/comment", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("comments", [])


def get_task_text(task_id: str) -> str:
    """
    All readable text of a task: description + every comment, concatenated.
    This is what we scan for Drive links and onboarding content.
    """
    task = get_task(task_id)
    parts = [task.get("name", ""), task.get("description") or task.get("text_content") or ""]
    for c in get_task_comments(task_id):
        parts.append(c.get("comment_text", ""))
    return "\n".join(p for p in parts if p)


def list_doc_pages(doc_id: str) -> list[dict]:
    """List the pages of a ClickUp Doc (v3)."""
    url = f"{API_V3}/workspaces/{CLICKUP_WORKSPACE_ID}/docs/{doc_id}/pages"
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("pages", [])


def get_doc_text(doc_id: str) -> str:
    """
    Full text of a ClickUp Doc (all pages concatenated). Used for the occasional
    case where onboarding info lives directly in a ClickUp Doc, not in Drive.
    """
    pages = list_doc_pages(doc_id)
    chunks = []
    for p in pages:
        title = p.get("name", "")
        body = p.get("content") or p.get("text_content") or ""
        chunks.append(f"# {title}\n{body}".strip())
    return "\n\n".join(c for c in chunks if c)


# ============================ OUTPUT side =====================================
#
# Decision (Manuel, jun 2026): every agent deliverable (Brand Document, strategy,
# content drafts, monthly report) is a REAL ClickUp Doc — kept in the Docs area and
# linked from a task so the team comments inline and the agent re-reads/updates it
# each cycle. HARD RULES:
#   - NEVER create a document as a List in the hierarchy.
#   - NEVER park it in a loose Space-level list — Docs belong organized under the
#     client's folder/space.
#   - Always link the Doc back to its task (comment) so it's reachable.

def add_task_comment(task_id: str, text: str) -> dict:
    """Post a comment on a task (used to drop the Doc link into the task)."""
    url = f"{API_V2}/task/{task_id}/comment"
    r = requests.post(url, headers=_headers(), json={"comment_text": text,
                                                     "notify_all": False}, timeout=30)
    r.raise_for_status()
    return r.json()


# ClickUp parent type enum (for Docs): 4=Space, 5=Folder, 6=List, 7=Everything, 12=Workspace
def create_document(name: str, parent_id: str, parent_type: int = 5) -> dict:
    """
    Create a real ClickUp Doc under a client container. Default parent_type=5
    (Folder) — the client's folder, NOT a loose List. NEVER use clickup_create_list
    to hold a document.
    """
    url = f"{API_V3}/workspaces/{CLICKUP_WORKSPACE_ID}/docs"
    payload = {
        "name": name,
        "parent": {"id": parent_id, "type": parent_type},
        "visibility": "PUBLIC",
        "create_page": False,
    }
    r = requests.post(url, headers=_headers(), json=payload, timeout=30)
    r.raise_for_status()
    doc = r.json()
    print(f"  📄 Created ClickUp Doc '{name}' → {doc.get('id')}")
    return doc


def create_document_page(doc_id: str, name: str, content_md: str) -> dict:
    """Add a markdown page to a ClickUp Doc."""
    url = f"{API_V3}/workspaces/{CLICKUP_WORKSPACE_ID}/docs/{doc_id}/pages"
    payload = {"name": name, "content": content_md, "content_format": "text/md"}
    r = requests.post(url, headers=_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def update_document_page(doc_id: str, page_id: str, content_md: str) -> dict:
    """
    Overwrite a Doc page's content — used to UPDATE a living reference (e.g. the
    Brand Document) each cycle without creating a new Doc.
    """
    url = f"{API_V3}/workspaces/{CLICKUP_WORKSPACE_ID}/docs/{doc_id}/pages/{page_id}"
    payload = {"content": content_md, "content_format": "text/md"}
    r = requests.put(url, headers=_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def doc_url(doc_id: str) -> str:
    """Public ClickUp URL for a Doc."""
    return f"https://app.clickup.com/{CLICKUP_WORKSPACE_ID}/docs/{doc_id}"


def publish_output_document(
    name: str,
    content_md: str,
    parent_id: str,
    link_from_task_id: str,
    parent_type: int = 5,
    page_name: str | None = None,
) -> dict:
    """
    The canonical OUTPUT operation. For every agent deliverable.

    1. Creates a real ClickUp Doc under the client's container (Folder by default —
       NEVER a loose List, NEVER as a List in the hierarchy).
    2. Writes the content as a page.
    3. Links the Doc back to the task via a comment, so the team reaches it from the
       task and leaves inline feedback, and the agent re-reads it next cycle.

    Returns {"doc_id", "url"}.
    """
    doc = create_document(name=name, parent_id=parent_id, parent_type=parent_type)
    doc_id = doc.get("id")
    create_document_page(doc_id, name=page_name or name, content_md=content_md)
    url = doc_url(doc_id)
    if link_from_task_id:
        add_task_comment(
            link_from_task_id,
            f"📄 Documento generado por Forky-G: **{name}**\n{url}\n\n"
            f"(Revisa y deja comentarios inline directamente en el Doc.)",
        )
        print(f"  🔗 Linked Doc to task {link_from_task_id}")
    return {"doc_id": doc_id, "url": url}


# ============================ INPUT orchestration =============================

# Lists whose content is NOT brand/content material — skipped during ingestion so
# we don't feed invoices, contracts, or admin notes into the brand designer.
SKIP_LISTS = {"administrativo", "pd lista vacía clientes", "creación sitio web"}


def ingest_task_materials(task_id: str, local_dir: str) -> dict:
    """
    Pull all materials a SINGLE task points to, following the convention:
      - attachments on the task   → downloaded locally (the 'doc adjunto' case)
      - Drive links in the task   → synced locally (rclone)
      - any inline task text       → returned as text
    Returns {"text", "files": [local paths], "drive": [...], "links": [...]}.
    """
    from drive_downloader import extract_drive_links, sync_drive_id
    from pathlib import Path

    task = get_task(task_id)
    text = get_task_text(task_id)
    links = extract_drive_links(text)
    files: list[str] = []

    # 1. Attachments on the task itself
    for att in get_task_attachments(task):
        dest = str(Path(local_dir) / "attachments" / f"{task_id}_{att['title']}")
        try:
            files.append(download_attachment(att["url"], dest))
            print(f"  📎 Downloaded attachment: {att['title']}")
        except Exception as e:
            print(f"  ⚠️ Attachment '{att['title']}' failed: {e}")

    # 2. Drive links in the text
    synced: list[str] = []
    for i, link in enumerate(links):
        if link["kind"] == "gdoc":
            continue  # Google Docs handled inside their synced folder / or as ClickUp Docs
        sub = str(Path(local_dir) / f"link_{i+1}_{link['id'][:8]}")
        synced.extend(str(f) for f in sync_drive_id(
            link["id"], sub, is_file=(link["kind"] == "file")))

    return {"text": text, "files": files, "drive": synced, "links": links}


def gather_client_materials(folder_id: str, local_dir: str,
                            skip_lists: set | None = None) -> dict:
    """
    Sweep an ENTIRE client folder for brand/content material — because materials
    are scattered: attachments live on tasks OR subtasks, across ONBOARDING, ADS,
    etc. (e.g. La Bruja's brand identity lives in a meeting Doc under the ADS task,
    not under onboarding).

    For every relevant list → every task & subtask:
      - download attachments (task or subtask)
      - sync Drive links found in the text
      - collect all text (descriptions + comments) into one corpus
    Admin/non-brand lists are skipped (see SKIP_LISTS).

    Returns {"text": <combined corpus>, "files": [local paths], "drive": [paths],
             "tasks_scanned": int, "lists_scanned": [names]}.
    NOTE: ClickUp Docs scattered in the folder (like meeting notes) are NOT
    auto-discovered here — pass their doc_ids to get_doc_text() and add the result
    to the text corpus. Folder-wide Doc discovery needs the workspace search API.
    """
    from drive_downloader import extract_drive_links, sync_drive_id
    from pathlib import Path

    skip = {s.lower() for s in (skip_lists if skip_lists is not None else SKIP_LISTS)}
    corpus: list[str] = []
    files: list[str] = []
    drive: list[str] = []
    tasks_scanned = 0
    lists_scanned: list[str] = []

    for lst in get_folder_lists(folder_id):
        if lst.get("name", "").strip().lower() in skip:
            continue
        lists_scanned.append(lst.get("name", ""))
        for task in get_list_tasks(lst["id"]):
            tasks_scanned += 1
            tid = task["id"]
            corpus.append(f"### Tarea: {task.get('name','')}\n"
                          f"{task.get('text_content') or task.get('description') or ''}")
            # attachments (works for tasks and subtasks alike)
            for att in get_task_attachments(task):
                dest = str(Path(local_dir) / "attachments" / f"{tid}_{att['title']}")
                try:
                    files.append(download_attachment(att["url"], dest))
                    print(f"  📎 {lst.get('name','')}/{task.get('name','')[:30]} → {att['title']}")
                except Exception as e:
                    print(f"  ⚠️ Attachment '{att['title']}' failed: {e}")
            # Drive links in text
            for i, link in enumerate(extract_drive_links(
                    task.get("text_content") or task.get("description") or "")):
                if link["kind"] == "gdoc":
                    continue
                sub = str(Path(local_dir) / "drive" / f"{tid}_{link['id'][:8]}")
                drive.extend(str(f) for f in sync_drive_id(
                    link["id"], sub, is_file=(link["kind"] == "file")))

    return {
        "text": "\n\n".join(c for c in corpus if c.strip()),
        "files": files,
        "drive": drive,
        "tasks_scanned": tasks_scanned,
        "lists_scanned": lists_scanned,
    }
