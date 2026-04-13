"""All Pygame drawing routines."""

from __future__ import annotations

import math
from typing import Optional

import pygame

from traffic_simulator.constants import *
from traffic_simulator.world import (
    LightPhase, World, Vehicle, angle_of, dist, lerp_pt,
)
from traffic_simulator.ui import Button, LightConfigPanel


class Renderer:
    """Draws the entire game frame."""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.font = pygame.font.SysFont("consolas", 16)
        self.font_sm = pygame.font.SysFont("consolas", 13)
        self.font_lg = pygame.font.SysFont("consolas", 20, bold=True)
        self.font_title = pygame.font.SysFont("consolas", 24, bold=True)

    # ------------------------------------------------------------------
    # Top-level draw
    # ------------------------------------------------------------------
    def draw(
        self,
        world: World,
        *,
        grid_snap: bool,
        mode: str,
        sim_running: bool,
        sim_speed: float,
        first_node_id: Optional[int],
        hovered_node_id: Optional[int],
        selected_node_id: Optional[int],
        selected_seg_id: Optional[int],
        selected_roundabout_id: Optional[int],
        buttons: list[Button],
        light_panel: LightConfigPanel,
        show_help: bool,
    ) -> None:
        self.screen.fill(C_BG)

        # canvas background
        pygame.draw.rect(self.screen, C_CANVAS_BG, (0, 0, CANVAS_W, SCREEN_H))

        if grid_snap:
            self._draw_grid()

        self._draw_roads(world, selected_seg_id)
        self._draw_roundabout_centers(world, selected_roundabout_id)
        self._draw_nodes(world, first_node_id, hovered_node_id, selected_node_id)
        self._draw_lights(world)
        self._draw_vehicles(world)
        self._draw_preview_line(world, first_node_id, grid_snap)
        self._draw_sidebar(world, buttons, mode, sim_running, sim_speed)

        if light_panel.visible:
            light_panel.draw(self.screen, self.font, self.font_sm)

        if show_help:
            self._draw_help()

    # ------------------------------------------------------------------
    # Grid
    # ------------------------------------------------------------------
    def _draw_grid(self) -> None:
        for x in range(0, CANVAS_W, GRID_SIZE):
            pygame.draw.line(self.screen, C_GRID, (x, 0), (x, SCREEN_H))
        for y in range(0, SCREEN_H, GRID_SIZE):
            pygame.draw.line(self.screen, C_GRID, (0, y), (CANVAS_W, y))

    # ------------------------------------------------------------------
    # Roads
    # ------------------------------------------------------------------
    def _draw_roads(self, world: World, selected_seg_id: Optional[int]) -> None:
        # Simple approach: just draw roads with thicker lines and filled circles at all nodes
        for s in world.segments.values():
            na, nb = world.nodes[s.node_a_id], world.nodes[s.node_b_id]
            ax, ay, bx, by = int(na.x), int(na.y), int(nb.x), int(nb.y)

            # highlight selection underneath
            if s.id == selected_seg_id:
                pygame.draw.line(self.screen, C_NODE_SELECTED, (ax, ay), (bx, by), ROAD_WIDTH + 4)

            # Draw main road
            pygame.draw.line(self.screen, C_ROAD, (ax, ay), (bx, by), ROAD_WIDTH)

            # dashed centre line
            length = dist(na.pos, nb.pos)
            if length > 20:
                dash, gap = 10, 8
                d = float(dash)
                while d < length - dash:
                    p1 = lerp_pt(na.pos, nb.pos, d / length)
                    p2 = lerp_pt(na.pos, nb.pos, min((d + dash) / length, 1.0))
                    pygame.draw.line(
                        self.screen, C_ROAD_LINE,
                        (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), 1,
                    )
                    d += dash + gap

        # Draw circles at ALL connection points to create smooth joins
        for n in world.nodes.values():
            if n.is_roundabout_center:
                continue
            connections = len(world.adj.get(n.id, []))
            if connections >= 2:  # At any connection point (not dead ends)
                # Draw circle with same radius as road width to create smooth corners
                pygame.draw.circle(self.screen, C_ROAD, (int(n.x), int(n.y)), ROAD_WIDTH // 2)

    # ------------------------------------------------------------------
    # Roundabout decorative centres
    # ------------------------------------------------------------------
    def _draw_roundabout_centers(self, world: World, selected_roundabout_id: Optional[int]) -> None:
        for n in world.nodes.values():
            if not n.is_roundabout_center:
                continue
            ix, iy, ir = int(n.x), int(n.y), int(n.roundabout_radius)

            # Highlight selected roundabout
            if n.id == selected_roundabout_id:
                # Draw selection glow
                pygame.draw.circle(self.screen, C_NODE_SELECTED, (ix, iy), ir + 6, 4)

            pygame.draw.circle(self.screen, C_ROUNDABOUT, (ix, iy), ir)
            pygame.draw.circle(self.screen, C_ROUNDABOUT_RING, (ix, iy), ir, 3)
            inner = int(n.roundabout_radius * 0.45)
            pygame.draw.circle(self.screen, C_CANVAS_BG, (ix, iy), inner)
            pygame.draw.circle(self.screen, C_ROUNDABOUT_RING, (ix, iy), inner, 2)

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------
    def _draw_nodes(
        self, world: World,
        first_node_id: Optional[int],
        hovered_node_id: Optional[int],
        selected_node_id: Optional[int],
    ) -> None:
        for n in world.nodes.values():
            if n.is_roundabout_center:
                continue

            # Only draw nodes that are selected, hovered, or have <=1 connection (endpoints)
            num_connections = len(world.adj.get(n.id, []))

            # Always show selected/hovered/first nodes
            if n.id in (selected_node_id, first_node_id, hovered_node_id):
                col, r = C_NODE, NODE_RADIUS
                if n.id in (selected_node_id, first_node_id):
                    col, r = C_NODE_SELECTED, NODE_RADIUS + 2
                elif n.id == hovered_node_id:
                    col, r = C_NODE_HOVER, NODE_RADIUS + 1
                pygame.draw.circle(self.screen, col, (int(n.x), int(n.y)), r)
                pygame.draw.circle(self.screen, (255, 255, 255, 60), (int(n.x), int(n.y)), r, 1)
            # Show smaller dots for endpoints (dead ends)
            elif num_connections <= 1:
                pygame.draw.circle(self.screen, C_NODE, (int(n.x), int(n.y)), 4)
            # For well-connected nodes, show a tiny dot
            else:
                pygame.draw.circle(self.screen, (100, 200, 140, 80), (int(n.x), int(n.y)), 2)

    # ------------------------------------------------------------------
    # Traffic lights
    # ------------------------------------------------------------------
    def _draw_lights(self, world: World) -> None:
        for l in world.lights.values():
            node = world.nodes.get(l.node_id)
            seg = world.segments.get(l.segment_id)
            if not node or not seg:
                continue
            other_id = seg.node_b_id if seg.node_a_id == l.node_id else seg.node_a_id
            other = world.nodes.get(other_id)
            if not other:
                continue
            ang = angle_of(other.pos, node.pos)
            lx = int(node.x + math.cos(ang) * 18)
            ly = int(node.y + math.sin(ang) * 18)

            # housing
            pygame.draw.circle(self.screen, (30, 30, 30), (lx, ly), 12)
            pygame.draw.circle(self.screen, (60, 60, 60), (lx, ly), 12, 2)

            # lit colour
            col = {LightPhase.RED: C_LIGHT_RED, LightPhase.YELLOW: C_LIGHT_YELLOW,
                   LightPhase.GREEN: C_LIGHT_GREEN}[l.phase]
            pygame.draw.circle(self.screen, col, (lx, ly), 7)

            # glow
            glow = pygame.Surface((30, 30), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*col, 40), (15, 15), 15)
            self.screen.blit(glow, (lx - 15, ly - 15))

    # ------------------------------------------------------------------
    # Vehicles
    # ------------------------------------------------------------------
    def _draw_vehicles(self, world: World) -> None:
        for v in world.vehicles.values():
            if not v.alive:
                continue
            pos = world.vehicle_pos(v)
            ang = world.vehicle_angle(v)
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            hw, hh = CAR_LENGTH / 2, CAR_WIDTH / 2
            corners = [
                (pos[0] + cos_a * hw - sin_a * hh, pos[1] + sin_a * hw + cos_a * hh),
                (pos[0] + cos_a * hw + sin_a * hh, pos[1] + sin_a * hw - cos_a * hh),
                (pos[0] - cos_a * hw + sin_a * hh, pos[1] - sin_a * hw - cos_a * hh),
                (pos[0] - cos_a * hw - sin_a * hh, pos[1] - sin_a * hw + cos_a * hh),
            ]

            # Emergency collision state - flash entire vehicle
            if v.in_collision:
                # Calculate blink phase (0.0 to 1.0)
                blink_cycle = (v.emergency_blink_phase / EMERGENCY_BLINK_RATE) % 1.0
                if blink_cycle < 0.5:
                    # Flash bright yellow during first half of cycle
                    pygame.draw.polygon(self.screen, (255, 220, 0), corners)
                else:
                    # Normal color during second half
                    pygame.draw.polygon(self.screen, v.color, corners)
            else:
                # Normal rendering
                pygame.draw.polygon(self.screen, v.color, corners)
            # windshield dot
            front = lerp_pt(pos, (pos[0] + cos_a * hw, pos[1] + sin_a * hw), 0.5)
            pygame.draw.circle(self.screen, (180, 220, 255), (int(front[0]), int(front[1])), 2)
            # waiting indicator
            if v.waiting:
                pygame.draw.circle(self.screen, C_LIGHT_RED, (int(pos[0]), int(pos[1]) - 12), 3)

    # ------------------------------------------------------------------
    # Preview line (road tool)
    # ------------------------------------------------------------------
    def _draw_preview_line(self, world: World, first_node_id: Optional[int], grid_snap: bool) -> None:
        if first_node_id is None:
            return
        fn = world.nodes.get(first_node_id)
        if not fn:
            return
        mx, my = pygame.mouse.get_pos()
        if mx >= CANVAS_W:
            return
        tx, ty = (round(mx / GRID_SIZE) * GRID_SIZE, round(my / GRID_SIZE) * GRID_SIZE) if grid_snap else (mx, my)
        pygame.draw.line(self.screen, (*C_ACCENT, 120), (int(fn.x), int(fn.y)), (tx, ty), 2)

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    def _draw_sidebar(
        self, world: World, buttons: list[Button],
        mode: str, sim_running: bool, sim_speed: float,
    ) -> None:
        pygame.draw.rect(self.screen, C_SIDEBAR, (CANVAS_W, 0, SIDEBAR_W, SCREEN_H))
        pygame.draw.line(self.screen, C_GRID, (CANVAS_W, 0), (CANVAS_W, SCREEN_H), 2)

        self.screen.blit(
            self.font_title.render("Traffic Sim", True, C_ACCENT),
            (CANVAS_W + 16, 20),
        )
        self.screen.blit(
            self.font_sm.render("v1.0", True, C_TEXT_DIM),
            (CANVAS_W + 170, 26),
        )

        mouse = pygame.mouse.get_pos()
        for b in buttons:
            b.hovered = b.rect.collidepoint(mouse)
            b.draw(self.screen, self.font_sm)

        # status block
        y = SCREEN_H - 180
        pygame.draw.line(self.screen, C_GRID, (CANVAS_W + 16, y), (CANVAS_W + SIDEBAR_W - 16, y))
        y += 12
        for line in (
            f"Mode: {mode.upper()}",
            f"Speed: {sim_speed:.2f}x  [+/-]",
            f"Nodes: {len(world.nodes)}",
            f"Roads: {len(world.segments)}",
            f"Lights: {len(world.lights)}",
            f"Cars: {len(world.vehicles)}",
            "RUNNING" if sim_running else "PAUSED",
        ):
            self.screen.blit(self.font_sm.render(line, True, C_TEXT_DIM), (CANVAS_W + 20, y))
            y += 19

    # ------------------------------------------------------------------
    # Help overlay
    # ------------------------------------------------------------------
    def _draw_help(self) -> None:
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        lines = [
            "TRAFFIC SIMULATOR — HELP",
            "",
            "Left Click      Place nodes & connect roads",
            "Right Click     Cancel / Deselect",
            "Del / Backspace Remove selected element",
            "",
            "Space           Toggle simulation",
            "+  /  −         Simulation speed",
            "S               Spawn a car",
            "C               Clear all cars",
            "G               Toggle grid snap",
            "R               Roundabout mode",
            "T               Traffic light mode",
            "F1              Toggle this help",
            "Esc             Close panels",
            "",
            "TRAFFIC LIGHTS:",
            "  In Light mode, click a node to place lights.",
            "  Click an existing light to configure its phases.",
            "  Adjust green / yellow / red durations and offset.",
            "",
            "ROUNDABOUTS:",
            "  In Roundabout mode, click to place a roundabout.",
            "  Connect external roads to roundabout ring nodes.",
        ]
        y = 80
        for i, line in enumerate(lines):
            f = self.font_lg if i == 0 else self.font
            col = C_ACCENT if i == 0 else C_TEXT
            self.screen.blit(f.render(line, True, col), (100, y))
            y += 28
