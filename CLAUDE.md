# CLAUDE.md — Instrucciones del agente Forky-G

Forky-G es el agente de contenido de **Pont Digital**. Ejecuta el ciclo mensual completo de
contenido para cada cliente (marca → estrategia → plan → producción → publicación → reporte).

**Lee este archivo completo antes de tocar código, ClickUp, o Drive.** Las reglas aquí son
obligatorias y reflejan cómo Pont Digital organiza su trabajo. No improvises el workflow.

---

## Cómo Pont Digital usa ClickUp (CONVENCIÓN ESTRUCTURAL — obligatoria)

ClickUp es el cerebro: las tareas son el estado del proceso, los documentos son input/output.
Pero **dónde** vive cada cosa sigue una convención estricta. Respétala siempre.

### INPUTS — lo que el agente CONSUME (materia prima que lee)

Transcripciones de onboarding, formulario del cliente, brand doc existente, moodboard /
referencias visuales, fotos y videos, info de la empresa.

- **Patrón normal: viven en Google Drive.** La tarea de ClickUp NO contiene la info —
  solo contiene **links** que apuntan a los archivos/carpetas de Drive. La descripción de la
  tarea de onboarding solo tiene la **estructura/plantilla** (los títulos de las secciones).
- **Excepción ocasional: Docs de ClickUp.** Para algunas tareas (ej. "Reuniones de PD"),
  Manuel guarda la info directamente en un Doc de ClickUp.

→ La ingesta debe **detectar cuál patrón usa cada tarea** y rutear:
```
Tarea ClickUp
   ├─ ¿links de Drive?  → extraer link → sacar folder/file ID → rclone sync → archivos locales
   └─ ¿Doc de ClickUp?  → clickup_get_document_pages → texto directo (sin Drive)
```
`drive_downloader.py` ya hace el sync por folder-ID. Falta construir el conector
"tarea ClickUp → extraer links de Drive → IDs". El MCP de ClickUp lee la tarea.

### OUTPUTS — lo que el agente PRODUCE (su trabajo terminado)

Documento de Marca, Estrategia + ideas, Plan de Contenido Mensual, borradores de posts,
Reporte Mensual.

**Regla de almacenamiento (NO romper) — decisión de Manuel, jun 2026: TODO en ClickUp Docs.**

1. **El documento es un Doc REAL de ClickUp**, guardado en el área de Docs **bajo el folder del
   cliente** (`clickup_create_document` con `parent.type=5` Folder). Así el agente lo relee y
   actualiza cada ciclo por API (referencia viva), y el equipo comenta inline.
   - ❌ **NUNCA** como Lista en la jerarquía (`clickup_create_list` es solo para tareas).
   - ❌ **NUNCA** en una lista suelta a nivel de Space — el Doc va organizado bajo el folder del cliente.

2. **La tarea referencia el Doc** con el link en un **comentario** (`clickup_create_task_comment`)
   para que el equipo lo encuentre desde la tarea y comente encima.

**Por qué ClickUp y no Drive:** el documento de marca/perfil es una *referencia viva* que el
agente relee y reescribe cada ciclo; en ClickUp lo lee/actualiza directo por API (sin bajar/subir
de Drive) y el equipo da feedback inline. Lo que estaba mal NO era usar ClickUp Docs — era la
ESTRUCTURA (lista suelta a nivel de Space / documentos como listas).

```
✅ BIEN:
   Doc de ClickUp (área de Docs, bajo el folder del cliente)
        ↑ link
   Tarea de ClickUp  →  link al Doc en un comentario

❌ MAL (lo que hace el agente hoy):
   Lista suelta "🤖 La Medusa Claude" a nivel de Space, separada del folder del cliente.
```

### Implementación en código

- **INPUT:** `src/clickup_client.py` (`get_task_text`, `get_doc_text`, `ingest_task_materials`,
  `gather_client_materials`) + `src/drive_downloader.py` (`extract_drive_links`, `sync_drive_id`).
  `gather_client_materials(folder_id)` barre todo el folder del cliente: tareas **y subtareas**,
  baja adjuntos de ambos niveles, sincroniza Drive links, junta el texto. Salta listas
  administrativas (`SKIP_LISTS`). Los Docs de ClickUp dispersos (ej. notas de reunión) NO se
  auto-descubren todavía: pasa su `doc_id` a `get_doc_text()` y súmalo al corpus.
  (Los inputs entran como vengan: links de Drive, adjuntos, o Docs de ClickUp.)
- **OUTPUT:** `src/clickup_client.py` → `publish_output_document(name, content_md, parent_id,
  link_from_task_id)` crea un Doc real bajo el folder del cliente (nunca lista) y lo enlaza desde
  la tarea. Para actualizar una referencia viva sin crear un Doc nuevo: `update_document_page()`.
- **Secrets requeridos** (env / GitHub secrets): `CLICKUP_API_TOKEN` (token personal `pk_…`,
  ClickUp → Settings → Apps → API Token) y `CLICKUP_WORKSPACE_ID` (= `90131122286` para Pont
  Digital). Ver README → GitHub Secrets. Las llamadas REST de ClickUp (v2 tasks/comments, v3 docs)
  deben validarse con una corrida real antes de producción.

### Resumen de la convención
| | Dónde vive | Cómo se referencia en ClickUp |
|---|---|---|
| **INPUTS** (el agente lee) | Drive / adjuntos / Docs ClickUp (como vengan) | Link en comentario, adjunto, o Doc de ClickUp |
| **OUTPUTS** (el agente produce) | Doc REAL de ClickUp, bajo el folder del cliente | Link al Doc en un comentario de la tarea |

### ⚠️ Limpieza pendiente de La Medusa (estructura, NO el medio)
Usar ClickUp Docs está bien. Lo que está mal es la ESTRUCTURA: el agente montó una Lista suelta
`🤖 La Medusa Claude — Junio 2026` (`901327417875`) a nivel de Space, separada del folder real
del cliente "La Medusa" (`901314898457`). Limpieza ideal: que los Docs y tareas del agente vivan
organizados bajo el folder del cliente, no en la lista suelta. LIMITACIÓN: el MCP de ClickUp no
puede borrar listas ni Docs (solo mover/borrar tareas) — esa parte la hace Manuel a mano. SIN
autorizar todavía. Confirmar con Manuel antes de mover/borrar nada.

---

## El ciclo (en orden)

1. **Documento de Marca** — Si no existe, créalo desde los materiales de onboarding.
   En Fase 1 el agente actúa como **director creativo (agnóstico de industria)** y genera
   **3 propuestas de identidad visual** desde los inputs; el cliente elige una → se vuelve el
   "Production Profile". Ver `src/brand_designer.py`.
2. **Estrategia + Ideas de Contenido** — basado en el Documento de Marca.
3. **Plan de Contenido Mensual** — requiere aprobación antes de seguir.
4. **Producción de Contenido** — footage real del Drive del cliente como base (NO imágenes IA
   salvo que no exista foto real y el cliente apruebe). Ver pipeline de video y los dos ROLES
   del agente más abajo.
5. **Publicación en Metricool** — agendar según el calendario.
6. **Reporte Mensual + Análisis** — analizar datos, escribir reporte, publicarlo en ClickUp.

---

## Los DOS roles del agente en producción de contenido (Fase 4)

La producción de un video tiene dos pasos, y en cada uno el agente actúa con un ROL distinto.
El rol es **genérico (agnóstico de industria)**; el contexto del cliente (Production Profile) se
inyecta. Es la BASE de Fase 4 — un buen guión hace que todo lo de abajo salga bien.

```
Brief del post
   → [ ROL 1: GUIONISTA ]  src/script_writer.py · write_script()
        Convierte el brief en el GUIÓN: escenas (qué se ve, duración, texto en pantalla).
        Reglas: hook en los primeros 3s · 3-5 escenas · cada escena 3-6s (el animador da ~5s)
        · respetar el máximo de la plataforma · ANIMAR footage real (describe el plano real a
        buscar, nunca inventa) · texto solo en 1-3 escenas + CTA final · on-brand.
        Salida = lista de escenas usable directo como post["scenes"].
   → [ ROL 2: DIRECTOR ]   src/content_director.py · generate_scene_prompts()
        Toma cada escena y escribe el PROMPT de Higgsfield (cámara, luz, movimiento).
        En modo "animate": describe SOLO cómo animar la imagen real, nunca inventa contenido.
   → Higgsfield anima el footage/foto REAL → color grade → texto → cards → watermark.
```

**Por qué importa:** los guiones que están hoy hardcodeados en `forky_g.py` (`CONTENT_PLANS`) se
escribieron con reglas viejas. La fuente correcta del guión es el rol GUIONISTA (o el doc de
borradores en ClickUp). NO hardcodear scripts — generarlos con `script_writer` o leerlos de ClickUp.

---

## Modelos de Claude (API)

| Tarea | Modelo | Notas |
|---|---|---|
| Propuestas de marca (Fase 1, 1 vez/cliente) | `claude-opus-4-8` | Tarea creativa de alto valor. `thinking: {"type": "adaptive"}`. Sin `budget_tokens` ni `temperature` (dan 400). |
| Guionista — `script_writer.py` (1 vez/post) | `claude-haiku-4-5` | Base de Fase 4. Override a `claude-sonnet-4-6` vía `FORKY_SCRIPT_MODEL` para más calidad. |
| Director de prompts — `content_director.py` (por escena) | `claude-haiku-4-5` | Volumen; barato |
| Análisis de clips (Claude Vision) | `claude-haiku-4-5` | Volumen, rápido y barato |
| Producción masiva de contenido | `claude-haiku-4-5` | Repetitivo; usar prompt caching del brand profile |

Llamadas a la API: HTTP directo con `requests` (no SDK), header `x-api-key` +
`anthropic-version: 2023-06-01`. Ver `src/clip_indexer.py` y `src/brand_designer.py`.

---

## Reglas de producción de video (resumen)

- Todo reel: intro card + escenas (footage real color-graded) + outro card + watermark.
  Footage crudo sin editar NO es aceptable. Mínimo 3 escenas con descripción.
- Pipeline activo (OPTION A): clip real → extraer frame → Higgsfield (start_image) → color
  grade → text overlay. Si no hay clip real → Higgsfield desde cero con el prompt de la escena.
- Todo encode FFmpeg DEBE incluir `-vf format=yuv420p -profile:v high -level 4.0 -pix_fmt
  yuv420p` (compatibilidad QuickTime/iOS/Android).
- Límites de duración por plataforma se aplican solos (`get_max_duration_for_post`).

(Los detalles completos del estándar de reels están en la memoria del proyecto y en `forky_g.py`.)

---

## Errores que NUNCA repetir

- NO crear documentos de output como Listas en la jerarquía de ClickUp (ver convención arriba).
- NO empezar a construir sin leer primero los documentos/tareas de ClickUp.
- NO generar imágenes IA cuando hay fotos reales del cliente en Drive.
- NO hardcodear contenido de posts en Python — leerlo de ClickUp.
- NO correr ciclos completos sin probar un post de punta a punta primero.
- Verificar rutas de output antes de llamadas de API costosas.
- El workflow se define en ClickUp, no se inventa en el código.
