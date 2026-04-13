# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Run directly (uv handles dependencies automatically)
uv run traffic-simulator

# Or: sync environment first, then run
uv sync
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
traffic-simulator
```

The entry point is defined in `pyproject.toml` as `traffic_simulator:main`, which calls `TrafficSimApp().run()`.

## Project Architecture

This is a **Pygame-based traffic simulation game** with a clean separation between data model, rendering, and UI:

### Module Responsibilities

- **[world.py](world.py)** — Core simulation data model and logic
  - `World`: owns all state (nodes, segments, lights, vehicles)
  - `RoadNode`, `RoadSegment`, `TrafficLight`, `Vehicle`: dataclasses for entities
  - Graph structure via `World.adj` (adjacency list mapping node_id → segment_ids)
  - Pathfinding uses BFS in `_find_path()`
  - Vehicle simulation in `tick()` handles movement and traffic light obedience

- **[renderer.py](renderer.py)** — Pure rendering (no state mutations)
  - `Renderer.draw()` is the top-level draw call
  - Renders grid, roads, roundabouts, nodes, traffic lights, vehicles, preview lines
  - All drawing uses data from `World`; renderer has no game logic

- **[ui.py](ui.py)** — Interactive widgets
  - `Button`: sidebar buttons with toggle states and callbacks
  - `LightConfigPanel`: modal overlay for editing traffic light phase durations and offsets

- **[app.py](app.py)** — Main game loop and event handling
  - `TrafficSimApp`: top-level coordinator
  - Pygame event loop in `run()`
  - Handles mouse/keyboard input and delegates to interaction modes
  - Builds sidebar buttons in `_build_sidebar()`
  - Three interaction modes: "road", "roundabout", "light"

- **[constants.py](constants.py)** — Shared constants (colors, dimensions, layout)

### Key Architecture Patterns

1. **Data model is fully separated from rendering**: `World` has no Pygame dependencies
2. **Event-driven UI**: user actions modify `World` state; renderer reads it each frame
3. **Mode-based interaction**: `self.mode` in `TrafficSimApp` determines click behavior
4. **Graph structure**: road network stored as adjacency list + dictionaries of nodes/segments
5. **Vehicle simulation**: vehicles follow pre-computed paths (BFS) and obey traffic lights at segment ends

### Traffic Light Mechanics

- Lights are placed on a `(segment_id, node_id)` pair (which end of the road)
- Lights have configurable phase durations: `[(LightPhase.GREEN, 5.0), (LightPhase.YELLOW, 1.5), (LightPhase.RED, 5.0)]`
- Phase offset allows staggering multiple lights
- Vehicles check lights when `t > 0.7` (approaching destination node) in `_tick_vehicle()`

### Roundabout Construction

`World.add_roundabout()` creates:
- A center node (marked `is_roundabout_center=True`, not selectable)
- Ring nodes at evenly-spaced angles
- Segments connecting ring nodes in a loop
- Users connect external roads to ring nodes

## Project Structure

```
traffic-simulator/
├── pyproject.toml              # project metadata & dependencies
├── README.md
└── src/
    └── traffic_simulator/      # main package
        ├── __init__.py         # package entry point
        ├── app.py              # main application / game loop
        ├── world.py            # data model (nodes, segments, lights, vehicles)
        ├── renderer.py         # all Pygame drawing code
        ├── ui.py               # sidebar buttons & traffic light config panel
        └── constants.py        # colours, sizes, layout values
```

## Development Notes

- Python 3.11+ required
- Uses `uv` for dependency management
- No tests or linting configured (yet)
- Package configured with hatchling build backend in `src/traffic_simulator/`
- Grid snapping: uses `GRID_SIZE=40` from constants; toggle with `G` key
- Simulation speed multiplier: adjust with `+` / `-` keys, stored in `sim_speed`
