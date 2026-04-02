# Agent System Guide

## Overview

Sistem agent kita terdiri dari 6 specialized agents yang bekerja dalam pipeline. Setiap agent punya role spesifik dan hanya bisa menggunakan tools yang ditentukan.

```
nav-orchestrator (planner)
  ├── nav-engine    (Phase 1: core engine)
  ├── nav-app       (Phase 2: app layer)
  ├── nav-integrate (Phase 3: wiring)
  ├── nav-review    (validator, setelah setiap phase)
  └── nav-test      (Phase 5: tests)
```

## Setup

### 1. Install Claude Code CLI

```bash
# Install global
npm install -g @anthropic-ai/claude-code

# Verifikasi
claude --version
```

Atau dari VS Code: `Cmd+Shift+P` → **"Claude Code: Install CLI to PATH"**

### 2. Verifikasi agents

```bash
cd ~/Documents/indoor-wayfinder
ls .claude/agents/

# Expected:
# nav-app.md  nav-engine.md  nav-integrate.md
# nav-orchestrator.md  nav-review.md  nav-test.md
```

### 3. Pastikan working directory benar

CLI dan agents harus dijalankan dari root project:
```bash
cd ~/Documents/indoor-wayfinder
```

Folder `.claude/agents/` dicari relatif dari sini. Kalau jalankan dari folder lain, agents tidak akan ditemukan.

---

## Cara Menjalankan Agent

### Metode 1: VS Code Chat Panel (Recommended)

Buka Claude Code panel di VS Code, lalu ketik:

```
@nav-orchestrator Build Phase 1: Core Engine
```

Atau panggil agent spesifik:
```
@nav-engine Build core/navigation/models.py
```

### Metode 2: CLI Terminal

```bash
# Full orchestration (semua phase berurutan)
claude --agent nav-orchestrator

# Agent spesifik
claude --agent nav-engine
claude --agent nav-app
claude --agent nav-integrate
claude --agent nav-review
claude --agent nav-test
```

### Metode 3: Dari dalam Claude Code session

Ketika sudah dalam session Claude Code biasa, minta dia spawn agent:

```
Tolong jalankan agent nav-engine untuk build Phase 1
```

Claude akan menggunakan Agent tool untuk mendelegasikan ke sub-agent.

---

## Agents Reference

### nav-orchestrator
- **Role**: Planner & delegator. Tidak menulis code.
- **Model**: Opus
- **Kapan pakai**: Untuk build full system atau multiple phases sekaligus.
- **Dia akan**: Merencanakan urutan, mendelegasikan ke builder agents, verifikasi hasil.

### nav-engine
- **Role**: Builder untuk core infrastructure.
- **Model**: Opus
- **Kapan pakai**: Phase 1 — navigation engine, pathfinding, graph, SVG utils.
- **Files**: `core/navigation/`, `core/playwright/`, `core/CircuitBreaker.py`, `app/utils/`
- **Fitur**: Akses context7 MCP untuk lookup dokumentasi Pydantic/library.

### nav-app
- **Role**: Builder untuk application layer.
- **Model**: Opus
- **Kapan pakai**: Phase 2 — controllers, services, tools, schemas.
- **Files**: `app/controllers/`, `app/services/`, `app/tools/`, `app/schemas/`, `app/repositories/`
- **Fitur**: Akses context7 MCP untuk lookup LangChain/LangGraph docs.

### nav-integrate
- **Role**: Editor-only. Modifikasi file existing.
- **Model**: Opus
- **Kapan pakai**: Phase 3 — wiring navigation ke template.
- **Files**: `config/setting.py`, `config/routes.py`, `app/Kernel.py`, `requirements.txt`, dll.
- **Constraint**: Tidak bisa Write (create file baru), hanya Edit file yang sudah ada.

### nav-review
- **Role**: Read-only reviewer. Tidak bisa edit code.
- **Model**: Opus
- **Kapan pakai**: Setelah setiap phase selesai, sebelum lanjut ke phase berikutnya.
- **Output**: Laporan `[FAIL]` / `[WARN]` / `[OK]` per file.
- **Constraint**: Hanya bisa Read, Grep, Glob. Tidak bisa Write/Edit/Bash.

### nav-test
- **Role**: Test writer & runner.
- **Model**: Sonnet (lebih cepat dan murah)
- **Kapan pakai**: Phase 5, atau setelah review passed.
- **Files**: `test/unit_test/`, `test/integration_test/`, `test/system_test/`

---

## Step-by-Step per Phase (Recommended)

### Phase 1: Core Engine (13 files)

**Agent**: `nav-engine`
**Dependency**: Tidak ada, bisa mulai langsung.
**Target files**:
- `core/navigation/__init__.py`, `engine.py`, `manager.py`
- `core/navigation/models.py`, `graph.py`, `pathfinding.py`, `segmenter.py`, `renderer.py`, `prompt.py`
- `core/playwright/__init__.py`, `engine.py`, `manager.py`
- `core/CircuitBreaker.py`
- `app/utils/GeoUtils.py`, `app/utils/SVGUtils.py`

**Langkah:**

```bash
# 1. Build
@nav-engine Build all Phase 1 files: core/navigation/, core/playwright/, CircuitBreaker.py, GeoUtils.py, SVGUtils.py

# 2. Review (otomatis di-prompt oleh hook setelah nav-engine selesai)
@nav-review Review Phase 1: check all files in core/navigation/, core/playwright/, core/CircuitBreaker.py, app/utils/GeoUtils.py, app/utils/SVGUtils.py

# 3. Fix jika ada [FAIL] dari review
@nav-engine Fix these issues from review: [paste review output]

# 4. Re-review sampai semua [OK]
@nav-review Re-review Phase 1 files
```

---

### Phase 2: App Layer (20 files)

**Agent**: `nav-app`
**Dependency**: Phase 1 harus selesai (import dari `core/navigation/`).
**Target files**:
- `app/schemas/`: NavigationInputSchema, NavigationOutputSchema, NavigationStateSchema, NavigationRouterOutputSchema, GraphAdminSchema (5 files)
- `app/repositories/`: GraphRepository, FloorAssetRepository (2 files)
- `app/tools/`: AISearchNavigate, Pathfinding, RouteRenderer, VirtualQueue, GraphQuery (5 files)
- `app/services/`: NavigationRouterService, NavigationAgentService, GuideMeAgentService, GraphInfoAgentService, InstructionGenService (5 files)
- `app/controllers/`: NavigationController, GraphAdminController (2 files)
- `app/command/`: graph_seed.py (1 file)

**Langkah:**

```bash
# 1. Build
@nav-app Build all Phase 2 files: schemas, repositories, tools, services, controllers, command

# 2. Review
@nav-review Review Phase 2: check all files in app/schemas/, app/repositories/, app/tools/, app/services/, app/controllers/Navigation*, app/controllers/GraphAdmin*, app/command/graph_seed.py

# 3. Fix jika perlu
@nav-app Fix these issues: [paste review output]
```

---

### Phase 3: Integration (8 file modifications)

**Agent**: `nav-integrate`
**Dependency**: Phase 1 + 2 harus selesai.
**Target files** (Edit only, bukan create):
- `config/setting.py` — tambah navigation env vars
- `config/routes.py` — tambah navigation routes di setup_routes()
- `routes/api/v1.py` — tambah navigation endpoints
- `routes/ws/v1.py` — tambah WebSocket /navigate
- `app/Kernel.py` — tambah GraphManager + PlaywrightManager ke lifespan
- `core/entrypoint.py` — tambah graph_seed entrypoint
- `requirements.txt` — tambah playwright, cairosvg
- `seeder/config.json` — tambah graph_seed

**Langkah:**

```bash
# 1. Edit existing files
@nav-integrate Wire navigation system into template: setting.py, routes.py, v1.py, ws/v1.py, Kernel.py, entrypoint.py, requirements.txt

# 2. Review
@nav-review Review Phase 3: check that setting.py, routes.py, Kernel.py, requirements.txt were modified correctly without breaking existing code

# 3. Fix jika perlu
@nav-integrate Fix these integration issues: [paste review output]
```

---

### Phase 4: Data Files (4 files)

**Agent**: `nav-engine` atau manual copy
**Dependency**: Tidak ada, bisa parallel dengan Phase 1.
**Target files**:
- `data/graphs/shlv.json` — merged graph data
- `data/floors/shlv/LT1.svg`, `LT2.svg`, `LT5.svg` — floor plan SVGs

**Langkah:**

```bash
# Option A: Agent
@nav-engine Create data files: merge current_data_sample/ into data/graphs/shlv.json, copy SVG floors to data/floors/shlv/

# Option B: Manual
# Copy SVGs dan merge JSON sendiri
```

---

### Phase 5: Tests (7 files)

**Agent**: `nav-test`
**Dependency**: Phase 1-3 harus selesai.
**Target files**:
- `test/unit_test/`: test_graph.py, test_pathfinding.py, test_segmenter.py, test_models.py (4 files)
- `test/integration_test/`: test_navigation_service.py, test_graph_repository.py (2 files)
- `test/system_test/`: test_navigation_flow.py (1 file)

**Langkah:**

```bash
# 1. Write tests
@nav-test Write all tests for the navigation system: unit tests for graph, pathfinding, segmenter, models; integration tests for navigation service and graph repository; system test for full navigation flow

# 2. Run tests
@nav-test Run all tests: cd ai-research-seamless-in-hospital-experienced && python -m pytest test/ -v

# 3. Fix failing tests
@nav-test Fix failing tests: [paste test output]
```

---

## Build Order & Dependencies

```
Phase 1 (Core Engine) ──────────┐
    13 files, no dependencies   │
                                ├── Phase 2 (App Layer)
                                │    20 files
Phase 4 (Data Files) ───────┐  │
    4 files, no dependencies │  │
                             │  ├── Phase 3 (Integration)
                             └──┤    8 file modifications
                                │
                                └── Phase 5 (Tests)
                                     7 files
```

**Urutan optimal:**
1. Phase 1 + Phase 4 (parallel, tidak ada dependency)
2. Phase 2 (setelah Phase 1 selesai)
3. Phase 3 (setelah Phase 1, 2, 4 selesai)
4. Phase 5 (setelah semua selesai)

**Agent per phase:**

| Phase | Agent | Action | Review |
|-------|-------|--------|--------|
| 1 | nav-engine | Write files | nav-review |
| 2 | nav-app | Write files | nav-review |
| 3 | nav-integrate | Edit existing files | nav-review |
| 4 | nav-engine / manual | Copy data | - |
| 5 | nav-test | Write + run tests | - |

---

## Monitoring Progress

### Dashboard HTML

```bash
npx serve .claude -l 3333
# Buka http://localhost:3333/dashboard.html
```

Dashboard auto-refresh tiap 3 detik dan menampilkan:
- Stats: files created/edited, agent sessions, total events
- Overall progress bar (target: 52 files)
- Agent Office: visual status per agent (IDLE/RUNNING/DONE)
- Build Phases: progress per phase dengan indicator
- Phase File Map: daftar file yang sudah masuk per phase
- Per-agent activity cards: log terpisah untuk setiap agent

Data berasal dari hooks di `.claude/settings.json` yang otomatis log ke `.claude/events.log` setiap kali agent Write/Edit file atau agent Start/Stop.

### Manual Check

```bash
# Lihat apa yang sudah dibuat
ls ai-research-seamless-in-hospital-experienced/core/navigation/ 2>/dev/null
ls ai-research-seamless-in-hospital-experienced/app/tools/ 2>/dev/null

# Lihat log activity
cat .claude/events.log

# Git diff untuk lihat semua perubahan
git diff --stat
```

---

## Auto-Review Hook

Di `.claude/settings.json`, ada hook `SubagentStop` yang otomatis trigger setelah builder agent (nav-engine, nav-app, nav-integrate) selesai. Hook ini mengingatkan untuk menjalankan nav-review sebelum lanjut ke phase berikutnya.

Setiap agent juga di-track individual (start/stop time) untuk monitoring di dashboard.

---

## Troubleshooting

### Agent kehabisan context
Gunakan `/compact` dalam session untuk compress context, atau mulai session baru dengan agent yang sama.

### Agent stuck atau loop
Tekan `Ctrl+C` untuk cancel, lalu jalankan ulang dengan instruksi yang lebih spesifik.

### File tidak sesuai template
Jalankan `@nav-review` dengan path spesifik:
```
@nav-review Review app/controllers/NavigationController.py against ChatbotController.py pattern
```

### Import error saat test
Pastikan Phase 1 dan 2 complete sebelum menjalankan tests. Cek:
```
@nav-review Check for import cycles in core/navigation/ and app/services/
```
