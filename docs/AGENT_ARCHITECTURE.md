# Agent Architecture

## Build System Agents

```mermaid
graph TD
    USER["Developer"] -->|"start build"| ORCH["nav-orchestrator<br/><i>Plans & delegates</i>"]

    ORCH -->|"Phase 1"| ENGINE["nav-engine<br/><i>core/navigation/<br/>core/playwright/<br/>utils/</i>"]
    ORCH -->|"Phase 2"| APP["nav-app<br/><i>controllers/<br/>services/<br/>tools/<br/>schemas/</i>"]
    ORCH -->|"Phase 3"| INTEG["nav-integrate<br/><i>Kernel.py<br/>routes.py<br/>setting.py</i>"]

    ENGINE -->|"validate"| REVIEW["nav-review<br/><i>Template compliance<br/>Code quality<br/>Business logic</i>"]
    APP -->|"validate"| REVIEW
    INTEG -->|"validate"| REVIEW

    REVIEW -->|"issues found"| ENGINE
    REVIEW -->|"issues found"| APP
    REVIEW -->|"issues found"| INTEG

    REVIEW -->|"passed"| TEST["nav-test<br/><i>Unit tests<br/>Integration tests<br/>System tests</i>"]

    TEST -->|"all green"| DONE["Phase Complete"]
    TEST -->|"failures"| ENGINE
    TEST -->|"failures"| APP

    style ORCH fill:#2c3e50,color:#fff
    style ENGINE fill:#2980b9,color:#fff
    style APP fill:#27ae60,color:#fff
    style INTEG fill:#8e44ad,color:#fff
    style REVIEW fill:#e74c3c,color:#fff
    style TEST fill:#f39c12,color:#fff
    style DONE fill:#1abc9c,color:#fff
```

## Navigation System Architecture (Runtime)

```mermaid
graph TD
    CLIENT["External Chatbot<br/>(WA/Website)"] -->|"WebSocket"| WS["WS /navigate"]
    CLIENT2["REST Client"] -->|"POST"| REST["POST /navigate"]

    WS --> NC["NavigationController<br/><i>LangGraph StateGraph</i>"]
    REST --> NC

    NC -->|"classify"| ROUTER["NavigationRouterService<br/><i>structured output</i>"]

    ROUTER -->|"navigation"| NAV["NavigationAgentService<br/><i>tool-calling</i>"]
    ROUTER -->|"guide_me"| GUIDE["GuideMeAgentService<br/><i>tool-calling</i>"]
    ROUTER -->|"info"| INFO["GraphInfoAgentService<br/><i>agentic loop</i>"]
    ROUTER -->|"fallback"| END["END"]

    NAV -->|"resolve"| T1["AISearchNavigate"]
    NAV -->|"pathfind"| T2["Pathfinding"]
    NAV -->|"render"| T3["RouteRenderer"]

    GUIDE -->|"queue"| T4["VirtualQueue"]
    INFO -->|"query"| T5["GraphQuery"]

    T1 -->|"fallback"| CB["CircuitBreaker"]
    CB -->|"OPEN"| LOCAL["HospitalGraph.resolve_destination()"]

    T2 --> ASTAR["A* Algorithm"]
    ASTAR --> GRAPH["HospitalGraph<br/><i>in-memory</i>"]

    T3 --> SEG["RouteSegmenter"]
    T3 --> REND["SegmentRenderer"]
    T3 --> PW["PlaywrightManager"]
    T3 --> S3["S3 Upload"]

    NAV -->|"per step"| INST["InstructionGenService<br/><i>simple chain</i>"]

    GRAPH -.->|"loaded from"| MONGO["MongoDB<br/>graph_data"]
    GRAPH -.->|"hot reload"| REDIS["Redis pub/sub<br/>graph:update"]

    style NC fill:#2c3e50,color:#fff
    style ROUTER fill:#e67e22,color:#fff
    style NAV fill:#2980b9,color:#fff
    style GUIDE fill:#27ae60,color:#fff
    style INFO fill:#8e44ad,color:#fff
    style GRAPH fill:#c0392b,color:#fff
    style MONGO fill:#16a085,color:#fff
```

## Data Flow: Admin Import

```mermaid
sequenceDiagram
    participant Editor as Floorplan Editor
    participant API as GraphAdminController
    participant Repo as GraphRepository
    participant Mongo as MongoDB
    participant GM as GraphManager
    participant Redis as Redis pub/sub
    participant Pods as Other Pods

    Editor->>API: POST /graph/import {nodes, floors}
    API->>Repo: save_graph(building_id, data)
    Repo->>Mongo: save snapshot to graph_versions
    Repo->>Mongo: upsert graph_data document
    Repo-->>API: new version number
    API->>GM: reload(building_id)
    GM->>Mongo: read new document
    GM->>GM: build HospitalGraph (atomic swap)
    API->>Redis: PUBLISH "graph:update"
    Redis->>Pods: notify all pods
    Pods->>Mongo: reload graph
    API->>Editor: {success, version}
```

## Phase Dependency Graph

```mermaid
graph LR
    P1["Phase 1<br/>Core Engine<br/><i>13 files</i>"] --> P2["Phase 2<br/>App Layer<br/><i>20 files</i>"]
    P2 --> P3["Phase 3<br/>Integration<br/><i>8 modifications</i>"]
    P4["Phase 4<br/>Data Files<br/><i>4 files</i>"] --> P3
    P3 --> P5["Phase 5<br/>Tests<br/><i>7 files</i>"]

    style P1 fill:#2980b9,color:#fff
    style P2 fill:#27ae60,color:#fff
    style P3 fill:#8e44ad,color:#fff
    style P4 fill:#e67e22,color:#fff
    style P5 fill:#f39c12,color:#fff
```

## Agent Capabilities Matrix

| Agent | Model | Tools | Memory | Can Write Code | Can Review |
|-------|-------|-------|--------|---------------|------------|
| nav-orchestrator | opus | Read, Glob, Grep, Agent | project | No | No |
| nav-engine | opus | Read, Write, Edit, Bash, Agent | project | Yes | No |
| nav-app | opus | Read, Write, Edit, Bash, Agent | project | Yes | No |
| nav-integrate | opus | Read, Edit, Grep, Glob, Bash | project | Edit only | No |
| nav-review | opus | Read, Grep, Glob | project | No | Yes |
| nav-test | sonnet | Read, Write, Edit, Bash | project | Tests only | No |
