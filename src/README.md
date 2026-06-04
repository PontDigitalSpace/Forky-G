# 🍴 Forky G — AI Content Agent
### Pont Digital · pont-digital.ca

Agente de contenido IA que ejecuta el ciclo mensual completo de contenido para clientes de Pont Digital.

---

## Stack

| Herramienta | Uso |
|---|---|
| **Claude API** (Sonnet 4) | Cerebro — estrategia, captions, coordinación |
| **Higgsfield / Veo 3.1** | Generación de video e imagen con IA |
| **ElevenLabs** | Voz en off en francés para Reels |
| **Descript** | Edición y exportación de video |
| **Google Drive** | Fuente de footage real del cliente |
| **GitHub Actions** | Ejecución automática mensual |

---

## Setup rápido

### 1. Clonar el repo
```bash
git clone https://github.com/pontdigital/forky-g.git
cd forky-g
pip install requests google-auth google-auth-oauthlib google-api-python-client
```

### 2. Configurar GitHub Secrets
En tu repo → Settings → Secrets → Actions → New repository secret:

| Secret | Dónde conseguirlo |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com/api-keys |
| `HIGGSFIELD_API_KEY` | higgsfield.ai/settings/api |
| `ELEVENLABS_API_KEY` | elevenlabs.io/app/settings/api-keys |
| `DESCRIPT_API_KEY` | web.descript.com/settings |
| `GDRIVE_FOLDER_ID` | ID de la carpeta raíz del cliente en Drive |

### 3. Ejecutar manualmente
En GitHub → Actions → "Forky G — Monthly Content Cycle" → Run workflow

O localmente:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export HIGGSFIELD_API_KEY=...
export ELEVENLABS_API_KEY=...
export DESCRIPT_API_KEY=...

cd src
python forky_g.py --client la_medusa --month junio_2026
```

---

## Estructura del proyecto

```
forky-g/
├── .github/
│   └── workflows/
│       └── content_cycle.yml    # GitHub Actions — ejecución automática
├── src/
│   ├── forky_g.py               # Script principal — orquesta todo
│   ├── higgsfield_client.py     # Cliente Higgsfield / Veo 3.1
│   ├── elevenlabs_client.py     # Cliente ElevenLabs TTS
│   └── descript_client.py       # Cliente Descript
├── config/
│   └── clients/                 # Config por cliente (próximamente)
├── output/                      # Videos e imágenes generadas (gitignored)
└── README.md
```

---

## Clientes activos

| Cliente | Estado | Ciclo |
|---|---|---|
| La Medusa | ✅ Activo | Junio 2026 |
| Scholeía | ⏳ Pendiente | — |
| Studies Québec | ⏳ Pendiente | — |
| BIMPro | ⏳ Pendiente | — |
| La Bruja | ⏳ Pendiente | — |
| El Kapricho | ⏳ Pendiente | — |

---

## Output por ciclo

Por cada post se genera:
- `video.mp4` — Reel final (video real o generado con Veo 3.1)
- `voiceover_fr.mp3` — Voz en off en francés (ElevenLabs)
- `slide_01.jpg ... slide_06.jpg` — Imágenes para carruseles
- `cycle_summary.json` — Resumen del ciclo con IDs de Descript

---

*Pont Digital · Inspire · Empower · Succeed*
