# File Specifications — Navigation System

> Complete list of files to create, grouped by execution order.
> Each file includes: purpose, pattern source, key classes/functions, and dependencies.

---

## Phase 1: Core Engine (no template dependencies, pure Python)

### 1.1 `core/navigation/models.py`
**Purpose:** Pydantic models for in-memory graph representation.
**Pattern:** Standalone Pydantic models (like `app/core/models.py` in reference).
**Classes:**
- `NodeData(BaseModel)` — id, name, floor, x, y, type, accessible, aliases, category, description, metadata
- `EdgeData(BaseModel)` — from_node (alias="from"), to_node (alias="to"), distance, tags, accessible, bidirectional. Config: populate_by_name=True
- `RouteStep(BaseModel)` — from_node, to_node, from_name, to_name, distance, floor, floor_change, instruction
- `RouteResponse(BaseModel)` — success, start, end, profile, total_distance, estimated_time_seconds, steps, nodes_visited, error

**Source logic:** `hospital-navigation/app/core/models.py`

### 1.2 `core/navigation/graph.py`
**Purpose:** In-memory graph with adjacency list, node lookup, fuzzy destination search.
**Pattern:** Engine-like (standalone class).
**Classes:**
- `HospitalGraph` — nodes dict, adjacency list, floors list
  - `from_mongo_doc(doc: dict) -> HospitalGraph` — builds from MongoDB document. Maps: cx->x, cy->y, objectName->name, categoryId->category, label->description. Derives edges from `connection[]` field. Calculates distances.
  - `get_node(id)`, `get_neighbors(id)`, `get_locations()`, `get_all_nodes()`
  - `resolve_destination(query) -> Optional[NodeData]` — 4-pass fuzzy: exact name, alias, partial name, partial alias
  - `euclidean_distance(id_a, id_b)`
  - `to_export_dict()` — back to editor-compatible format
- `GraphRegistry` — dict of building_id -> HospitalGraph

**Source logic:** `hospital-navigation/app/core/graph.py`
**Key change:** `from_mongo_doc()` instead of `from_json_file()`. Handle UUID room IDs and j{N} junction IDs. Edges derived from `connection[]`, not from separate edges array.

### 1.3 `core/navigation/pathfinding.py`
**Purpose:** A* algorithm with profile-based edge weighting.
**Pattern:** Engine-like (pure functions).
**Functions:**
- `_edge_weight(edge, distance, profile) -> Optional[float]`
- `_heuristic(graph, node_id, goal_id) -> float`
- `astar(graph, start_id, goal_id, profile) -> Optional[list[str]]`
- `find_route(graph, start_id, goal_id, profile) -> RouteResponse`
**Constants:** WALKING_SPEED_MS=1.4, MAP_RATIO=20.0, FLOOR_PENALTY=30.0

**Source logic:** `hospital-navigation/app/core/pathfinding.py` (copy with minimal changes)

### 1.4 `app/utils/GeoUtils.py`
**Purpose:** Geometry helpers for direction detection and bounding boxes.
**Functions:**
- `cross_product(a, b, c) -> float`
- `angle_between(a, b, c) -> float` (degrees)
- `classify_turn(angle) -> str` (straight/slight_left/left/sharp_left/...)
- `bounding_box(points, padding) -> tuple[float, float, float, float]`

### 1.5 `core/navigation/segmenter.py`
**Purpose:** Split path into navigation segments at turn points, floor changes, landmarks, max distance.
**Classes:**
- `RouteSegment(BaseModel)` — nodes, floor, distance, direction, landmarks, start_node, end_node
- `RouteSegmenter`
  - `segment(graph, path, profile) -> list[RouteSegment]`
  - `_detect_turns(graph, path) -> list[int]` (indices where significant turn occurs)
  - `_split_by_floor(graph, path) -> list[list[str]]`
  - `_split_by_distance(segment, max_m=80) -> list[RouteSegment]`

### 1.6 `app/utils/SVGUtils.py`
**Purpose:** SVG string manipulation — inject route overlay, crop viewBox.
**Functions:**
- `inject_route_overlay(svg_str, points, color, stroke_width) -> str` — insert polyline before </svg>
- `inject_markers(svg_str, start_point, end_point) -> str` — start circle (green) + end circle (red)
- `inject_arrows(svg_str, points, turn_indices) -> str` — arrowhead polygons
- `inject_labels(svg_str, labels) -> str` — text elements for landmarks
- `crop_viewbox(svg_str, bbox) -> str` — set viewBox attribute
- `inject_turn_badge(svg_str, point, direction) -> str` — "BELOK ->" badge

### 1.7 `core/navigation/renderer.py`
**Purpose:** Combine SVG utils to render a complete segment image.
**Classes:**
- `SegmentRenderer`
  - `render_segment(base_svg, segment, graph) -> str` — returns cropped SVG string
  - `render_all_segments(base_svgs, segments, graph) -> list[str]`

### 1.8 `core/navigation/prompt.py`
**Purpose:** Prompt templates for LLM instruction generation.
**Constants:**
- `NAVIGATION_ROUTER_PROMPT` — intent classification prompt
- `NAVIGATION_AGENT_PROMPT` — core navigation prompt (Bahasa Indonesia)
- `INSTRUCTION_GEN_PROMPT` — per-step instruction generation prompt
- `GRAPH_INFO_PROMPT` — informational queries prompt
- `GUIDE_ME_PROMPT` — virtual queue + navigation prompt

### 1.9 `core/navigation/manager.py`
**Purpose:** GraphManager — loads from MongoDB, manages lifecycle, hot reload.
**Pattern:** `core/queue/manager.py` (classmethod-based manager).
**Classes:**
- `GraphManager`
  - `_graphs: dict[str, HospitalGraph]`
  - `_repository: GraphRepository`
  - `async load_all_buildings()` — read all graph_data docs from MongoDB, build HospitalGraph per building
  - `get(building_id) -> HospitalGraph`
  - `async reload(building_id)` — re-read from MongoDB, build new graph, atomic pointer swap
  - `async start_listener()` — Redis pub/sub on "graph:update" channel
  - `async stop_listener()`

### 1.10 `core/navigation/__init__.py`
```python
from .manager import GraphManager
from .pathfinding import find_route
from .segmenter import RouteSegmenter
```

### 1.11 `core/CircuitBreaker.py`
**Purpose:** Generic circuit breaker for external API calls.
**Pattern:** Standalone like `core/BaseAgent.py`.
**Class:** `CircuitBreaker`
- States: CLOSED, OPEN, HALF_OPEN
- `__init__(name, failure_threshold=3, recovery_timeout=30, fallback=None)`
- `async call(func, *args, **kwargs)` — execute with circuit breaker logic

### 1.12 `core/playwright/__init__.py`
```python
from .manager import PlaywrightManager
```

### 1.13 `core/playwright/engine.py`
**Purpose:** Browser instance wrapper, SVG->PNG rendering.
**Class:** `PlaywrightEngine`
- `__init__(browser)`
- `async render_svg_to_png(svg_string, width, height) -> bytes`
- `async health_check() -> bool`

### 1.14 `core/playwright/manager.py`
**Purpose:** Browser pool lifecycle.
**Pattern:** `core/queue/manager.py`.
**Class:** `PlaywrightManager`
- `__init__(pool_size=3)`
- `async start()` — launch browser instances
- `async stop()` — close all browsers
- `async acquire() -> PlaywrightEngine` — get instance from pool
- `release(engine)` — return to pool

---

## Phase 2: App Layer (depends on Phase 1 + template)

### 2.1 `app/schemas/NavigationInputSchema.py`
**Classes:**
- `NavigationRequest(BaseModel)` — query, building_id, current_floor, current_location, profile, output_format, start_id, end_id
- `NavigationDirectRequest(BaseModel)` — from_node, to_node, profile, building_id

### 2.2 `app/schemas/NavigationOutputSchema.py`
**Classes:**
- `RouteMetaResponse(BaseModel)` — type="route_meta", total_steps, total_distance_m, estimated_time_s, floors_involved, correlation_id
- `RouteStepResponse(BaseModel)` — type="route_step", step, total_steps, floor, instruction, image_url, svg_data, distance_m, landmarks

### 2.3 `app/schemas/NavigationRouterOutputSchema.py`
**Classes:**
- `NavigationIntent(str, Enum)` — navigation, guide_me, info, fallback
- `NavigationRouterOutput(BaseModel)` — intent (NavigationIntent), confidence (float), reasoning (str)

### 2.4 `app/schemas/GraphCrudSchema.py`
**Classes:**
- `GraphImportPayload(BaseModel)` — building_id, building_name, nodes (list[dict]), floors (list[int])
- `GraphExportResponse(BaseModel)` — building_id, version, nodes, floors
- `RoomSyncResponse(BaseModel)` — building_id, version, rooms (list[dict])

### 2.5 `app/schemas/WebSocketMessageSchema.py`
**Classes:**
- `WSRouteMeta(BaseModel)` — type, total_steps, total_distance_m, estimated_time_s, floors_involved, correlation_id
- `WSRouteStep(BaseModel)` — type, step, total_steps, floor, instruction, image_url, svg_data, distance_m, landmarks
- `WSRouteComplete(BaseModel)` — type, destination, message
- `WSError(BaseModel)` — type, code, message

### 2.6 `app/repositories/GraphRepository.py`
**Purpose:** MongoDB CRUD for graph_data + graph_versions.
**Pattern:** Singleton with MongoDb instance.
**Class:** `GraphRepository`
- `async get_graph(building_id) -> dict | None`
- `async get_all_graphs() -> list[dict]`
- `async save_graph(building_id, data, updated_by) -> int` (returns new version)
- `async get_rooms(building_id) -> list[dict]`
- `async get_version_history(building_id, limit) -> list[dict]`

Singleton: `graphRepository = GraphRepository()`

### 2.7 `app/repositories/FloorAssetRepository.py`
**Purpose:** MongoDB CRUD for floor_assets.
**Class:** `FloorAssetRepository`
- `async get_floor(building_id, floor_number) -> dict | None`
- `async save_floor(building_id, floor_number, svg_s3_url)`
- `async get_all_floors(building_id) -> list[dict]`

Singleton: `floorAssetRepository = FloorAssetRepository()`

### 2.8 `app/tools/AISearchNavigate.py`
**Purpose:** Resolve destination via AI Search REST API with CircuitBreaker fallback.
**Pattern:** `@tool` decorator wrapping class instance.
**Fallback:** Local HospitalGraph.resolve_destination() when circuit is OPEN.

### 2.9 `app/tools/Pathfinding.py`
**Purpose:** Wrap core/navigation pathfinding as LangChain tool.
**Pattern:** `@tool` decorator.

### 2.10 `app/tools/RouteRenderer.py`
**Purpose:** Segment + render + optional Playwright PNG + S3 upload.
**Pattern:** `@tool` decorator.

### 2.11 `app/tools/VirtualQueue.py`
**Purpose:** REST API call to Virtual Queue service.
**Pattern:** `@tool` decorator with HttpClientUtils.

### 2.12 `app/tools/GraphQuery.py`
**Purpose:** Room lookup, floor info, building info from HospitalGraph.
**Pattern:** `@tool` decorator.

### 2.13 `app/services/NavigationRouterService.py`
**Purpose:** Classify user intent.
**Pattern:** `ChatbotRouterService.py` (structured output, no tools).
**Output model:** `NavigationRouterOutput`
**Intents:** navigation, guide_me, info, fallback

### 2.14 `app/services/NavigationAgentService.py`
**Purpose:** Core navigation — resolve destination, pathfind, render, instruct.
**Pattern:** `DoctorAgentService.py` (tool-calling with manual execution).
**Tools:** AISearchNavigate, Pathfinding, RouteRenderer

### 2.15 `app/services/GuideMeAgentService.py`
**Purpose:** Virtual queue lookup + delegate to NavigationAgent.
**Pattern:** `DoctorAgentService.py` (tool-calling).
**Tools:** VirtualQueue

### 2.16 `app/services/GraphInfoAgentService.py`
**Purpose:** Answer informational queries about hospital facilities.
**Pattern:** `QNAAgentService.py` (agentic loop).
**Tools:** GraphQuery

### 2.17 `app/services/InstructionGenService.py`
**Purpose:** Generate natural language instruction per route segment.
**Pattern:** `SampleAgentService.py` (simple chain, no tools).
**Input:** segment data (direction, landmarks, distance). **Output:** Bahasa Indonesia instruction string.

### 2.18 `app/controllers/NavigationController.py`
**Purpose:** LangGraph orchestrator — router -> agent routing.
**Pattern:** `ChatbotController.py`.
**Nodes:** router, nav_agent, guide_me, graph_info
**Methods:** `start_navigating(input)`, `handle_websocket(websocket)`
**Singleton:** `navigationController = NavigationController()`

### 2.19 `app/controllers/GraphAdminController.py`
**Purpose:** Graph CRUD + import/export (no LangGraph).
**Pattern:** `SampleController.py`.
**Methods:** `import_graph(payload)`, `export_graph(building_id)`, `sync_rooms(building_id)`
**Singleton:** `graphAdminController = GraphAdminController()`

### 2.20 `app/command/graph_seed.py`
**Purpose:** Seed graph data from JSON files to MongoDB.
**Reads:** `data/graphs/shlv.json` or `current_data_sample/*.json`
**Writes:** MongoDB `graph_data` collection via GraphRepository.

---

## Phase 3: Integration (modify existing template files)

### 3.1 `config/setting.py` — ADD navigation env vars
```python
# Navigation
AI_SEARCH_BASE_URL: Optional[str] = None
AI_SEARCH_TIMEOUT_S: Optional[float] = 5.0
AI_SEARCH_WEBHOOK_URL: Optional[str] = None
VIRTUAL_QUEUE_BASE_URL: Optional[str] = None
PLAYWRIGHT_POOL_SIZE: Optional[int] = 3
PLAYWRIGHT_TIMEOUT_MS: Optional[int] = 5000
GRAPH_DATA_DIR: Optional[str] = "data/graphs"
FLOOR_SVG_DIR: Optional[str] = "data/floors"
S3_ROUTE_IMAGE_PREFIX: Optional[str] = "navigation/rendered/"
GRAPH_SYNC_REDIS_CHANNEL: Optional[str] = "graph:update"
ROUTE_CACHE_TTL_S: Optional[int] = 3600
CB_FAILURE_THRESHOLD: Optional[int] = 3
CB_RECOVERY_TIMEOUT_S: Optional[int] = 30
DEFAULT_BUILDING: Optional[str] = "shlv"
```

### 3.2 `config/routes.py` — ADD navigation + admin routes
- Include navigation router with POST /navigate
- Include graph admin router with /graph/* endpoints
- Add WebSocket /ws/v1/navigate

### 3.3 `routes/api/v1.py` — ADD endpoints
- `POST /navigate` -> navigationController.start_navigating
- `POST /route` -> direct pathfinding (no LLM)
- `POST /graph/import` -> graphAdminController.import_graph
- `GET /graph/export/{building_id}` -> graphAdminController.export_graph
- `GET /rooms/sync` -> graphAdminController.sync_rooms
- `GET /buildings` -> list buildings
- `GET /buildings/{id}/graph` -> full graph data
- `GET /locations` -> list rooms/facilities

### 3.4 `routes/ws/v1.py` — ADD WebSocket endpoint
- `WS /navigate` -> navigationController.handle_websocket

### 3.5 `app/Kernel.py` — ADD to lifespan
Startup: GraphManager.load_all_buildings(), PlaywrightManager.start()
Shutdown: PlaywrightManager.stop()

### 3.6 `core/entrypoint.py` — ADD graph_seed entrypoint
### 3.7 `requirements.txt` — ADD playwright, cairosvg
### 3.8 `seeder/config.json` — ADD graph_seed to run order

---

## Phase 4: Data Files (copy/create)

### 4.1 `data/graphs/shlv.json` — merged graph from current_data_sample
### 4.2 `data/floors/shlv/1.svg` — copy from hospital-navigation
### 4.3 `data/floors/shlv/2.svg` — copy from hospital-navigation
### 4.4 `data/floors/shlv/5.svg` — copy from hospital-navigation

---

## Phase 5: Tests

### 5.1 `test/unit_test/test_pathfinding.py`
### 5.2 `test/unit_test/test_segmenter.py`
### 5.3 `test/unit_test/test_geo_utils.py`
### 5.4 `test/unit_test/test_svg_utils.py`
### 5.5 `test/integration_test/test_navigation_pipeline.py`
### 5.6 `test/integration_test/test_graph_crud.py`
### 5.7 `test/system_test/test_websocket_navigate.py`

---

## Dependency Graph

```
Phase 1 (no deps):
  models.py -> graph.py -> pathfinding.py
  GeoUtils.py -> segmenter.py
  SVGUtils.py -> renderer.py
  prompt.py (standalone)
  CircuitBreaker.py (standalone)
  playwright/ (standalone)

Phase 2 (depends on Phase 1 + template):
  repositories/ -> manager.py (GraphManager uses GraphRepository)
  schemas/ (standalone)
  tools/ (depends on core/navigation + repositories)
  services/ (depends on tools + BaseAgent)
  controllers/ (depends on services + LangGraph)

Phase 3 (depends on Phase 2):
  setting.py, routes.py, Kernel.py, v1.py, ws/v1.py

Phase 4 (anytime):
  data files

Phase 5 (depends on Phase 1-3):
  tests
```
