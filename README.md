# Traffic Simulator

A birds-eye 2D traffic simulation game built with Pygame. Design road networks with roundabouts and programmable traffic lights, then simulate traffic flowing through them.

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)
![Pygame](https://img.shields.io/badge/pygame-2.5+-green)

## Quick Start

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
# Clone and enter the project
git clone <repo-url>
cd traffic-simulator

# Run (uv installs dependencies automatically)
uv run traffic-simulator
```

That's it — `uv run` creates the virtual environment, installs pygame, and launches the game in one step.

### Alternative: sync first, then run manually

```bash
uv sync                          # create venv + install deps
source .venv/bin/activate        # activate (Linux/macOS)
# .venv\Scripts\activate         # activate (Windows)
traffic-simulator                # run via entry point
```

## Controls

| Key / Input       | Action                             |
|--------------------|-------------------------------------|
| **Left Click**     | Place / connect road nodes          |
| **Right Click**    | Cancel current action / deselect    |
| **Space**          | Toggle simulation pause             |
| **S**              | Spawn a car                         |
| **R**              | Roundabout placement mode           |
| **T**              | Traffic light placement mode        |
| **G**              | Toggle grid snap                    |
| **+  /  −**        | Speed up / slow down simulation     |
| **Del / Backspace**| Remove selected element             |
| **C**              | Clear all vehicles                  |
| **F1**             | Toggle help overlay                 |
| **Esc**            | Close panels                        |

## How to Play

1. **Build roads** — Click to place nodes; keep clicking to chain road segments. Right-click to stop.
2. **Place roundabouts** — Press `R`, then click on the canvas.
3. **Add traffic lights** — Press `T`, then click any road node. Click an existing light to configure its green / yellow / red durations and phase offset.
4. **Simulate** — Press `Space` to start. Press `S` to spawn cars (or toggle *Auto Spawn* in the sidebar). Cars pathfind between random endpoints and obey traffic lights.

## Project Structure

```
traffic-simulator/
├── pyproject.toml              # project metadata & dependencies
├── .python-version             # pinned Python version for uv
├── README.md
└── src/
    └── traffic_simulator/
        ├── __init__.py         # package entry point
        ├── app.py              # main application / game loop
        ├── world.py            # data model (nodes, segments, lights, vehicles)
        ├── renderer.py         # all Pygame drawing code
        ├── ui.py               # sidebar buttons & traffic light config panel
        └── constants.py        # colours, sizes, layout values
```

## License

MIT
