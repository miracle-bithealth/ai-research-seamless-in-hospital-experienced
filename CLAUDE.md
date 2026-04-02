# CLAUDE.md — AI Smart Hospital Navigation System

> Read this FIRST before making any changes.

## Project Identity

**Project:** AI Smart Hospital Navigation System (Seamless Patient Experience)
**Template:** `ai-research-template-v2.2` (internal FastAPI + LangChain/LangGraph framework)
**Target Dir:** `ai-research-seamless-in-hospital-experienced/`
**Purpose:** Indoor wayfinding — step-by-step navigation with cropped floorplan images + natural language instructions, delivered via WhatsApp and Website chatbot.

---

## Code Style Rules

- No emoji in code or comments
- No excessive comments — only where logic is non-obvious
- No docstrings unless the function signature is ambiguous
- No "AI-generated" patterns (verbose explanations, unnecessary type annotations on obvious variables)
- Keep imports grouped: stdlib, third-party, local
- Follow template naming exactly — do not invent new conventions

---

## How It Works (End-to-End)

```
Patient: "Mau ke toilet di mana?"
  |
External Chatbot (WA/Website) -> WebSocket connect
  |
NavigationRouterService classifies intent -> "navigation"
  |
NavigationAgentService:
  1. AISearchNavigate tool -> resolve "toilet" -> node UUID
  2. Pathfinding tool -> A* on in-memory HospitalGraph -> path [j63, j20, ...]
  3. RouteRenderer tool:
     a. Segment route by turn points (cross product angle detection)
     b. For each segment: SVG overlay + crop viewBox
     c. WA: Playwright -> PNG -> S3 upload -> URL
     d. Web: return SVG string directly
  4. InstructionGenService -> LLM generates Bahasa Indonesia instruction per step
  |
Stream via WebSocket: route_meta -> route_step (xN) -> route_complete
```

---

## Storage Architecture

```
MongoDB (config/mongoDb.py + motor async)
  graph_data        1 doc per building = full graph snapshot
  graph_versions    audit trail (previous snapshots)
  floor_assets      floor SVG S3 references

Redis (config/cache.py)
  route cache       route:{building}:{start}:{end}:{profile}
  SVG cache         svg:{building}:{floor}
  pub/sub           channel "graph:update" for multi-pod sync

S3 (app/traits/Uploader/)
  SVG originals     floors/{building}/{floor}.svg
  Rendered PNGs     navigation/rendered/{hash}_step{n}.png

In-Memory (core/navigation/manager.py)
  HospitalGraph     per building, loaded from MongoDB at startup
                    hot-reloaded on admin update (atomic pointer swap)
```

---

## Data Format (from Floorplan Editor)

Data comes in TWO files per floor:

### base_data (room metadata)
```json
{
  "id": "f12a668f-953d-4184-af79-de0b768d2ecd",
  "slug": "lt1-pharmacy-farmasi",
  "label": "Pharmacy / Farmasi",
  "floor": "1",
  "wings": "",
  "room-type": "PHARMACY",
  "keywords": "obat, resep dokter, apoteker...",
  "aliases": "apotek, farmasi, tebus resep...",
  "description": "Fasilitas pelayanan farmasi klinis..."
}
```

### spatial_data (graph nodes + connections)
```json
{
  "id": "f12a668f-953d-4184-af79-de0b768d2ecd",
  "type": "room",
  "connection": ["j9", "j10"],
  "cx": 639,
  "cy": 355
}
```

Room IDs are UUIDs. Junction IDs are `j{N}`. The `connection` field is the adjacency list. Edges are derived from connections (not stored separately). Distance is calculated at load time from coordinates.

### MongoDB Document Structure (merged)

```json
{
  "_id": "shlv",
  "building_name": "Siloam Hospitals Lippo Village",
  "version": 1,
  "floors": [1, 2, 5],
  "nodes": [
    {
      "id": "f12a668f-...",
      "type": "room",
      "floor": 1,
      "cx": 639,
      "cy": 355,
      "slug": "lt1-pharmacy-farmasi",
      "objectName": "Pharmacy / Farmasi",
      "label": "Fasilitas pelayanan farmasi...",
      "categoryId": "PHARMACY",
      "wings": "",
      "aliases": ["apotek", "farmasi", "tebus resep"],
      "keywords": ["obat", "resep dokter"],
      "connection": ["j9"]
    },
    {
      "id": "j9",
      "type": "junction",
      "floor": 1,
      "cx": 585,
      "cy": 354,
      "connection": ["j8", "j10", "f12a668f-..."]
    }
  ],
  "updated_by": "admin",
  "updated_at": "2026-03-30T10:00:00Z"
}
```

### Field Mapping: MongoDB -> In-Memory (HospitalGraph)

```
MongoDB field    -> In-memory field
cx               -> x (float)
cy               -> y (float)
objectName       -> name
categoryId       -> category
label            -> description
floor (str "1")  -> floor (int 1)
```

### Node Counts (current data)

| Floor | Junctions | Rooms | Total |
|-------|-----------|-------|-------|
| LT1   | ~46       | 27    | 73    |
| LT2   | ~108      | 41    | 149   |
| LT5   | ~218      | 43    | 261   |

---

## Technical Decisions (DO NOT CHANGE)

| Decision | Choice | Why |
|----------|--------|-----|
| Graph storage | MongoDB (1 doc/building) | Editor exports JSON, store as-is |
| Image rendering | SVG for web, Playwright->PNG for WA | SVG files are 15-23MB from Inkscape |
| Pathfinding | Custom A* (no external lib) | Supports dynamic edge weighting |
| Direction detection | Cross product of 3 consecutive nodes | SVG Y-axis inverted |
| LLM for instructions | Gemini Flash Lite 2.5 via template | Cost-effective, fast |
| Language | Bahasa Indonesia | Target: Indonesian hospital patients |
| Distance unit | "~20 langkah" (steps) not meters | More intuitive for indoor |
| Orientation | Landmark-based, not compass | "Berdiri menghadap Koperasi" |

---

## A* Pathfinding

- f(n) = g(n) + h(n)
- Heuristic: Euclidean + floor penalty (30.0 per floor diff)
- MAP_RATIO = 20.0 (pixels to meters)
- WALKING_SPEED = 1.4 m/s
- Profiles: default, wheelchair (skip stairs/inaccessible), elderly (stairs x3), emergency (shortest)

## Direction Detection (Cross Product)

```
cross = (B.x-A.x)*(C.y-B.y) - (B.y-A.y)*(C.x-B.x)
```
SVG Y-axis inverted: cross > 0 = RIGHT, cross < 0 = LEFT, |angle| < 15 = STRAIGHT.

## Route Segmentation

Split at: significant turn (>30 deg), floor transition, key landmark, max distance (>80m real).

## SVG Pipeline

String manipulation only (NO XML parser — files are 257K lines).
Inject before `</svg>`: polyline, arrowheads, start/end markers, landmark labels.
Crop via viewBox with 80px padding.

---

## Template Conventions (MUST FOLLOW)

### File Naming

| Location | Convention | Example |
|----------|-----------|---------|
| `app/controllers/` | `{Name}Controller.py` | `NavigationController.py` |
| `app/services/` | `{Name}Service.py` | `NavigationAgentService.py` |
| `app/tools/` | `{Name}.py` | `AISearchNavigate.py` |
| `app/schemas/` | `{Name}Schema.py` | `NavigationInputSchema.py` |
| `app/repositories/` | `{Name}Repository.py` | `GraphRepository.py` |
| `app/utils/` | `{Name}Utils.py` | `SVGUtils.py` |
| `app/command/` | `{name}.py` (lowercase) | `graph_seed.py` |
| `core/` standalone | `{Name}.py` (PascalCase) | `CircuitBreaker.py` |
| `core/{package}/` | `__init__.py` + `engine.py` + `manager.py` | `core/navigation/` |

### Controller Pattern

```python
from app.generative import manager as AiManager
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

class NavigationController:
    def __init__(self):
        self.llm = AiManager.gemini_mini()
        self.router = NavigationRouterService(llm=self.llm)
        self.nav_agent = NavigationAgentService(llm=self.llm, ...)
        self.build_graph(checkpoint=InMemorySaver())

    def build_graph(self, checkpoint=None):
        workflow = StateGraph(NavigationState)
        # ... add nodes, edges, compile
        self.graph = workflow.compile(checkpointer=checkpoint)

    async def start_navigating(self, input_data):
        result = await self.graph.ainvoke(initial_state, config=config)
        return response_success(result)

navigationController = NavigationController()
```

### Agent Pattern (BaseAgent)

Three sub-patterns:
1. **Router** (structured output): `ChatbotRouterService.py` pattern
2. **Tool-calling** (manual execution): `DoctorAgentService.py` pattern
3. **Agentic loop** (loop until done): `QNAAgentService.py` pattern

All agents: `async def __call__(self, state) -> dict`

### MongoDB Pattern

```python
from config.mongoDb import MongoDb

db = MongoDb()
doc = await db.find_one({"_id": "shlv"}, collection="graph_data")
await db.update_upsert({"_id": id}, data, collection="graph_data")
cursor = db.get_cursor({}, collection="graph_data")
```

### Response Pattern

```python
from app.utils.HttpResponseUtils import response_success, response_error
return response_success(data)
```

---

## Reference Files (read these for pattern examples)

| Pattern | Reference File |
|---------|---------------|
| Controller + LangGraph | `app/controllers/ChatbotController.py` |
| Router agent (structured output) | `app/services/ChatbotRouterService.py` |
| Tool-calling agent | `app/services/DoctorAgentService.py` |
| Agentic loop agent | `app/services/QNAAgentService.py` |
| Simple chain agent | `app/services/SampleAgentService.py` |
| Schema with enums | `app/schemas/ChatbotRouterOutputSchema.py` |
| Core package pattern | `core/cache/` or `core/queue/` |
| MongoDB usage | `core/AsyncRedisMongoDbSaver.py` |
| Tool definition | `app/tools/retrievaldoctor.py` |
| HTTP client | `app/traits/HttpClientUtils.py` |

---

## Existing Backend Reference

Business logic reference (NOT template-compliant, reference only):
- `hospital-navigation/app/core/graph.py` — HospitalGraph class
- `hospital-navigation/app/core/pathfinding.py` — A* algorithm
- `hospital-navigation/app/core/models.py` — data models
- `hospital-navigation/app/ai/navigator.py` — LLM agentic loop
- `hospital-navigation/app/ai/tools.py` — tool handlers

Data files:
- `current_data_sample/` — real production data (base_data + spatial_data per floor)
- `hospital-navigation/app/data/graphs/shlv.json` — old format graph
- `hospital-navigation/data_shlv/` — original SVG floor plans + Floorplan Editor

---

## External Dependencies

| System | Protocol | Usage |
|--------|----------|-------|
| AI Search | REST API | resolve natural language -> node IDs |
| Virtual Queue | REST API | get queue destination for Guide Me |
| External Chatbot | WebSocket (consumer) | connects to our WS, receives steps |
