"""Main application: game loop, input handling, sidebar construction."""

from __future__ import annotations

import math
import sys
from typing import Optional

import pygame

from traffic_simulator.constants import (
    CANVAS_W, FPS, GRID_SIZE, NODE_RADIUS, ROAD_WIDTH, SCREEN_H, SCREEN_W, SIDEBAR_W,
    C_DANGER, C_TEXT_DIM,
)
from traffic_simulator.world import World, dist, angle_of
from traffic_simulator.ui import Button, LightConfigPanel
from traffic_simulator.renderer import Renderer


def _snap(pos: tuple[float, float]) -> tuple[float, float]:
    return (round(pos[0] / GRID_SIZE) * GRID_SIZE,
            round(pos[1] / GRID_SIZE) * GRID_SIZE)


def _point_near_segment(p, a, b, threshold=12) -> bool:
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return dist(p, a) <= threshold
    t = max(0, min(1, ((p[0]-a[0])*dx + (p[1]-a[1])*dy) / (dx*dx + dy*dy)))
    proj = (a[0] + t*dx, a[1] + t*dy)
    return dist(p, proj) <= threshold


class TrafficSimApp:
    """Top-level application object."""

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Traffic Simulator")
        self.clock = pygame.time.Clock()
        self.renderer = Renderer(self.screen)

        self.world = World()
        self.running = True
        self.sim_running = False
        self.sim_speed = 1.0
        self.grid_snap = True
        self.show_help = False
        self.auto_spawn = False
        self.auto_spawn_timer = 0.0
        self.auto_spawn_interval = 2.0

        # interaction state
        self.mode = "road"
        self.first_node_id: Optional[int] = None
        self.hovered_node_id: Optional[int] = None
        self.selected_node_id: Optional[int] = None
        self.selected_seg_id: Optional[int] = None
        self.selected_light_id: Optional[int] = None
        self.dragging_node_id: Optional[int] = None

        self.light_panel = LightConfigPanel()
        self._build_sidebar()

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    def _build_sidebar(self) -> None:
        self.buttons: list[Button] = []
        bx = CANVAS_W + 16
        bw = SIDEBAR_W - 32
        y = 70

        def _btn(label, cb, *, toggle=False, color=None):
            nonlocal y
            b = Button((bx, y, bw, 34), label, cb, toggle=toggle, color=color)
            self.buttons.append(b)
            y += 42
            return b

        self.btn_road = _btn("Road Tool  [Click]", lambda: self._set_mode("road"), toggle=True)
        self.btn_road.active = True
        self.btn_roundabout = _btn("Roundabout  [R]", lambda: self._set_mode("roundabout"), toggle=True)
        self.btn_light = _btn("Traffic Light  [T]", lambda: self._set_mode("light"), toggle=True)

        y += 10
        self.btn_sim = _btn("Start Sim  [Space]", self._toggle_sim, toggle=True)
        self.btn_spawn = _btn("Spawn Car  [S]", lambda: self.world.spawn_vehicle_at_random())
        self.btn_auto = _btn("Auto Spawn", self._toggle_auto_spawn, toggle=True)
        self.btn_clear = _btn("Clear Cars  [C]", lambda: self.world.vehicles.clear())

        y += 10
        self.btn_grid = _btn("Grid Snap  [G]", self._toggle_grid, toggle=True)
        self.btn_grid.active = True
        self.btn_help = _btn("Help  [F1]", lambda: setattr(self, "show_help", not self.show_help), toggle=True)
        self.btn_clear_all = _btn("Clear All", self._clear_all, color=C_DANGER)

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self.first_node_id = None
        for b in (self.btn_road, self.btn_roundabout, self.btn_light):
            b.active = False
        {"road": self.btn_road, "roundabout": self.btn_roundabout,
         "light": self.btn_light}.get(mode, self.btn_road).active = True

    def _toggle_sim(self) -> None:
        self.sim_running = not self.sim_running
        self.btn_sim.label = "Pause Sim  [Space]" if self.sim_running else "Start Sim  [Space]"
        self.btn_sim.active = self.sim_running

    def _toggle_auto_spawn(self) -> None:
        self.auto_spawn = not self.auto_spawn
        self.btn_auto.active = self.auto_spawn

    def _toggle_grid(self) -> None:
        self.grid_snap = not self.grid_snap
        self.btn_grid.active = self.grid_snap

    def _clear_all(self) -> None:
        self.world = World()
        self.first_node_id = self.selected_node_id = self.selected_seg_id = self.selected_light_id = None

    # ------------------------------------------------------------------
    # Finders
    # ------------------------------------------------------------------
    def _find_node_at(self, pos, radius=15) -> Optional[int]:
        for n in self.world.nodes.values():
            if not n.is_roundabout_center and dist(pos, n.pos) < radius:
                return n.id
        return None

    def _find_segment_at(self, pos) -> Optional[int]:
        for s in self.world.segments.values():
            na, nb = self.world.nodes[s.node_a_id], self.world.nodes[s.node_b_id]
            if _point_near_segment(pos, na.pos, nb.pos, ROAD_WIDTH // 2 + 4):
                return s.id
        return None

    def _find_light_at(self, pos, radius=14) -> Optional[int]:
        for l in self.world.lights.values():
            node = self.world.nodes.get(l.node_id)
            seg = self.world.segments.get(l.segment_id)
            if not node or not seg:
                continue
            other_id = seg.node_b_id if seg.node_a_id == l.node_id else seg.node_a_id
            other = self.world.nodes.get(other_id)
            if not other:
                continue
            ang = angle_of(other.pos, node.pos)
            lx = node.x + math.cos(ang) * 20
            ly = node.y + math.sin(ang) * 20
            if dist(pos, (lx, ly)) < radius:
                return l.id
        return None

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()
            if self.sim_running:
                self.world.tick(dt * self.sim_speed)
                if self.auto_spawn:
                    self.auto_spawn_timer += dt * self.sim_speed
                    if self.auto_spawn_timer >= self.auto_spawn_interval:
                        self.auto_spawn_timer = 0
                        self.world.spawn_vehicle_at_random()
            self.renderer.draw(
                self.world,
                grid_snap=self.grid_snap,
                mode=self.mode,
                sim_running=self.sim_running,
                sim_speed=self.sim_speed,
                first_node_id=self.first_node_id,
                hovered_node_id=self.hovered_node_id,
                selected_node_id=self.selected_node_id,
                selected_seg_id=self.selected_seg_id,
                buttons=self.buttons,
                light_panel=self.light_panel,
                show_help=self.show_help,
            )
            pygame.display.flip()
        pygame.quit()
        sys.exit()

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def _handle_events(self) -> None:
        mouse = pygame.mouse.get_pos()
        self.hovered_node_id = self._find_node_at(mouse) if mouse[0] < CANVAS_W else None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._on_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self._on_left_click(mouse)
                elif event.button == 3:
                    self._on_right_click()
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.dragging_node_id = None
            elif event.type == pygame.MOUSEMOTION:
                if self.dragging_node_id:
                    n = self.world.nodes.get(self.dragging_node_id)
                    if n:
                        p = _snap(mouse) if self.grid_snap else mouse
                        n.x, n.y = p

    def _on_key(self, key: int) -> None:
        if key == pygame.K_SPACE:
            self._toggle_sim()
        elif key == pygame.K_g:
            self._toggle_grid()
        elif key == pygame.K_r:
            self._set_mode("roundabout")
        elif key == pygame.K_t:
            self._set_mode("light")
        elif key == pygame.K_s:
            self.world.spawn_vehicle_at_random()
        elif key == pygame.K_c:
            self.world.vehicles.clear()
        elif key == pygame.K_F1:
            self.show_help = not self.show_help
            self.btn_help.active = self.show_help
        elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.sim_speed = min(5.0, self.sim_speed + 0.25)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.sim_speed = max(0.25, self.sim_speed - 0.25)
        elif key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            if self.selected_light_id:
                self.world.remove_light(self.selected_light_id)
                self.selected_light_id = None
            elif self.selected_seg_id:
                self.world.remove_segment(self.selected_seg_id)
                self.selected_seg_id = None
            elif self.selected_node_id:
                self.world.remove_node(self.selected_node_id)
                self.selected_node_id = None
        elif key == pygame.K_ESCAPE:
            if self.light_panel.visible:
                self.light_panel.close()

    def _on_left_click(self, mouse: tuple[int, int]) -> None:
        if self.light_panel.visible and self.light_panel.handle_click(mouse):
            return
        for b in self.buttons:
            if b.handle(mouse, True):
                return
        if mouse[0] >= CANVAS_W:
            return

        if self.mode == "road":
            self._click_road(mouse)
        elif self.mode == "roundabout":
            self._click_roundabout(mouse)
        elif self.mode == "light":
            self._click_light(mouse)

    def _on_right_click(self) -> None:
        self.first_node_id = self.selected_node_id = self.selected_seg_id = self.selected_light_id = None

    # -- mode-specific clicks --

    def _click_road(self, pos) -> None:
        nid = self._find_node_at(pos)
        if self.first_node_id is None:
            if nid:
                self.first_node_id = nid
            else:
                p = _snap(pos) if self.grid_snap else pos
                n = self.world.add_node(*p)
                self.first_node_id = n.id
            self.selected_node_id = self.first_node_id
        else:
            if nid and nid != self.first_node_id:
                self.world.add_segment(self.first_node_id, nid)
                self.first_node_id = nid
            elif nid is None:
                p = _snap(pos) if self.grid_snap else pos
                n = self.world.add_node(*p)
                self.world.add_segment(self.first_node_id, n.id)
                self.first_node_id = n.id
            self.selected_node_id = self.first_node_id

    def _click_roundabout(self, pos) -> None:
        p = _snap(pos) if self.grid_snap else pos
        self.world.add_roundabout(p[0], p[1])

    def _click_light(self, pos) -> None:
        lid = self._find_light_at(pos)
        if lid:
            self.light_panel.open(self.world.lights[lid])
            return
        nid = self._find_node_at(pos, 20)
        if nid:
            for sid in self.world.adj.get(nid, []):
                self.world.add_light(sid, nid)
            return
        sid = self._find_segment_at(pos)
        if sid:
            seg = self.world.segments[sid]
            na, nb = self.world.nodes[seg.node_a_id], self.world.nodes[seg.node_b_id]
            closer = seg.node_a_id if dist(pos, na.pos) < dist(pos, nb.pos) else seg.node_b_id
            self.world.add_light(sid, closer)
