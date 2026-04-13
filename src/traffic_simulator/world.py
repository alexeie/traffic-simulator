"""Data model: road network, traffic lights, vehicles, and simulation logic."""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from traffic_simulator.constants import C_CAR_COLORS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def lerp_pt(a: tuple, b: tuple, t: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def angle_of(a: tuple, b: tuple) -> float:
    return math.atan2(b[1] - a[1], b[0] - a[0])


# ---------------------------------------------------------------------------
# Enums / data classes
# ---------------------------------------------------------------------------

class LightPhase(Enum):
    RED = auto()
    YELLOW = auto()
    GREEN = auto()


@dataclass
class RoadNode:
    x: float
    y: float
    id: int
    is_roundabout_center: bool = False
    roundabout_radius: float = 0

    @property
    def pos(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass
class RoadSegment:
    node_a_id: int
    node_b_id: int
    id: int
    one_way: bool = False


@dataclass
class TrafficLight:
    segment_id: int
    node_id: int          # which end of the segment the light sits on
    id: int
    phases: list = field(default_factory=lambda: [
        (LightPhase.GREEN, 5.0),
        (LightPhase.YELLOW, 1.5),
        (LightPhase.RED, 5.0),
    ])
    current_phase_idx: int = 0
    timer: float = 0.0
    offset: float = 0.0   # phase offset in seconds

    @property
    def phase(self) -> LightPhase:
        return self.phases[self.current_phase_idx][0]

    def tick(self, dt: float) -> None:
        self.timer += dt
        duration = self.phases[self.current_phase_idx][1]
        if self.timer >= duration:
            self.timer -= duration
            self.current_phase_idx = (self.current_phase_idx + 1) % len(self.phases)


@dataclass
class Vehicle:
    id: int
    current_node_id: int     # node we're currently leaving from
    next_node_id: int        # node we're traveling toward
    t: float = 0.0           # 0‥1 progress along current segment
    speed: float = 120.0     # pixels / second
    color: tuple = field(default_factory=lambda: random.choice(C_CAR_COLORS))
    waiting: bool = False
    alive: bool = True


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------

class World:
    """Owns the entire simulation state."""

    def __init__(self) -> None:
        self.nodes: dict[int, RoadNode] = {}
        self.segments: dict[int, RoadSegment] = {}
        self.lights: dict[int, TrafficLight] = {}
        self.vehicles: dict[int, Vehicle] = {}
        self._next_id = 1
        self.adj: dict[int, list[int]] = {}   # node_id → [segment_ids]

    # -- id generation --
    def _new_id(self) -> int:
        i = self._next_id
        self._next_id += 1
        return i

    # -- nodes --
    def add_node(self, x: float, y: float, *, is_rb: bool = False, rb_radius: float = 0) -> RoadNode:
        n = RoadNode(x, y, self._new_id(), is_rb, rb_radius)
        self.nodes[n.id] = n
        self.adj[n.id] = []
        return n

    def remove_node(self, nid: int) -> None:
        for sid in list(self.adj.get(nid, [])):
            self.remove_segment(sid)
        self.adj.pop(nid, None)
        self.nodes.pop(nid, None)

    # -- segments --
    def add_segment(self, a_id: int, b_id: int) -> Optional[RoadSegment]:
        if a_id == b_id:
            return None
        # avoid duplicates
        for sid in self.adj.get(a_id, []):
            seg = self.segments[sid]
            if {seg.node_a_id, seg.node_b_id} == {a_id, b_id}:
                return None
        s = RoadSegment(a_id, b_id, self._new_id())
        self.segments[s.id] = s
        self.adj[a_id].append(s.id)
        self.adj[b_id].append(s.id)
        return s

    def remove_segment(self, sid: int) -> None:
        seg = self.segments.pop(sid, None)
        if not seg:
            return
        for nid in (seg.node_a_id, seg.node_b_id):
            lst = self.adj.get(nid, [])
            if sid in lst:
                lst.remove(sid)
        # remove any lights on this segment
        for lid in [l.id for l in self.lights.values() if l.segment_id == sid]:
            self.lights.pop(lid, None)

    # -- traffic lights --
    def add_light(self, seg_id: int, node_id: int) -> TrafficLight:
        for l in self.lights.values():
            if l.segment_id == seg_id and l.node_id == node_id:
                return l
        tl = TrafficLight(seg_id, node_id, self._new_id())
        self.lights[tl.id] = tl
        return tl

    def remove_light(self, lid: int) -> None:
        self.lights.pop(lid, None)

    def get_light_at(self, seg_id: int, node_id: int) -> Optional[TrafficLight]:
        for l in self.lights.values():
            if l.segment_id == seg_id and l.node_id == node_id:
                return l
        return None

    # -- roundabouts --
    def add_roundabout(self, cx: float, cy: float, radius: float = 60, spokes: int = 4):
        center = self.add_node(cx, cy, is_rb=True, rb_radius=radius)
        ring_nodes: list[RoadNode] = []
        for i in range(spokes):
            angle = (2 * math.pi * i) / spokes - math.pi / 2
            nx = cx + radius * math.cos(angle)
            ny = cy + radius * math.sin(angle)
            ring_nodes.append(self.add_node(nx, ny))
        # Create one-way segments around the ring (clockwise)
        for i in range(len(ring_nodes)):
            seg = self.add_segment(ring_nodes[i].id, ring_nodes[(i + 1) % len(ring_nodes)].id)
            if seg:
                seg.one_way = True  # Enforce one-way flow
        return center, ring_nodes

    # -- vehicles --
    def spawn_vehicle_at_random(self) -> Optional[Vehicle]:
        # Find all nodes with connections (not roundabout centers)
        valid_nodes = [n for n in self.nodes.values()
                      if len(self.adj.get(n.id, [])) >= 1 and not n.is_roundabout_center]
        if not valid_nodes:
            return None

        # Pick a random starting node
        start_node = random.choice(valid_nodes)

        # Pick a random connected neighbor
        connected_segs = self.adj.get(start_node.id, [])
        if not connected_segs:
            return None

        first_seg = self.segments[random.choice(connected_segs)]
        next_node_id = first_seg.node_b_id if first_seg.node_a_id == start_node.id else first_seg.node_a_id

        v = Vehicle(self._new_id(), start_node.id, next_node_id)
        self.vehicles[v.id] = v
        return v


    # -- simulation --
    def tick(self, dt: float) -> None:
        for l in self.lights.values():
            l.tick(dt)
        dead: list[int] = []
        for v in self.vehicles.values():
            if not v.alive:
                dead.append(v.id)
                continue
            self._tick_vehicle(v, dt)
        for vid in dead:
            self.vehicles.pop(vid, None)

    def _tick_vehicle(self, v: Vehicle, dt: float) -> None:
        # Get current and next nodes
        na = self.nodes.get(v.current_node_id)
        nb = self.nodes.get(v.next_node_id)

        if not na or not nb:
            # Invalid nodes, remove vehicle
            print(f"💀 DESPAWNED Vehicle {v.id}: invalid nodes")
            v.alive = False
            return

        seg_len = dist(na.pos, nb.pos)

        # Skip very short segments
        while seg_len < 1:
            v.current_node_id = v.next_node_id
            v.t = 0
            # Pick next random neighbor
            next_node = self._pick_random_neighbor(v.current_node_id, exclude=v.current_node_id)
            if not next_node:
                v.alive = False
                return
            v.next_node_id = next_node
            na = self.nodes[v.current_node_id]
            nb = self.nodes[v.next_node_id]
            seg_len = dist(na.pos, nb.pos)

        # Find matching segment id
        seg_id = None
        for sid in self.adj.get(na.id, []):
            seg = self.segments.get(sid)
            if seg and {seg.node_a_id, seg.node_b_id} == {na.id, nb.id}:
                seg_id = sid
                break

        # Obey traffic lights near the destination node
        if seg_id and v.t > 0.7:
            light = self.get_light_at(seg_id, nb.id)
            if light and light.phase == LightPhase.RED:
                v.waiting = True
                return
            if light and light.phase == LightPhase.YELLOW and v.t > 0.85:
                v.waiting = True
                return

        v.waiting = False
        v.t += (v.speed * dt) / seg_len

        # When reaching the next node, pick a new random direction
        if v.t >= 1.0:
            v.t = 0.0
            v.current_node_id = v.next_node_id

            # Pick next random neighbor (avoid going back where we came from)
            next_node = self._pick_random_neighbor(v.current_node_id, exclude=na.id)
            if not next_node:
                v.alive = False
                return

            v.next_node_id = next_node

    def _pick_random_neighbor(self, node_id: int, exclude: Optional[int] = None) -> Optional[int]:
        """Pick a random neighboring node, optionally excluding one (to avoid U-turns)
        Respects one-way segments."""
        connected_segs = self.adj.get(node_id, [])
        if not connected_segs:
            return None

        neighbors = []
        for sid in connected_segs:
            seg = self.segments[sid]

            # Check if this is a valid direction to travel
            if seg.one_way:
                # One-way: can only go from node_b to node_a (reversed for roundabouts)
                if seg.node_b_id == node_id:
                    neighbor_id = seg.node_a_id
                else:
                    continue  # Can't travel backwards on one-way
            else:
                # Two-way: can go either direction
                neighbor_id = seg.node_b_id if seg.node_a_id == node_id else seg.node_a_id

            if neighbor_id != exclude:
                neighbors.append(neighbor_id)

        # If no neighbors except the one we came from, allow U-turn (only on two-way roads)
        if not neighbors and exclude is not None:
            for sid in connected_segs:
                seg = self.segments[sid]
                if not seg.one_way:  # Only allow U-turns on two-way roads
                    neighbor_id = seg.node_b_id if seg.node_a_id == node_id else seg.node_a_id
                    neighbors.append(neighbor_id)

        return random.choice(neighbors) if neighbors else None

    # -- convenience queries --
    def vehicle_pos(self, v: Vehicle) -> tuple[float, float]:
        na = self.nodes.get(v.current_node_id)
        nb = self.nodes.get(v.next_node_id)
        if not na or not nb:
            return (0.0, 0.0)

        # Base position along the road
        base_pos = lerp_pt(na.pos, nb.pos, v.t)

        # Calculate offset to the right (6 pixels to the right of center)
        angle = angle_of(na.pos, nb.pos)
        # Right side is perpendicular: angle + π/2 (90 degrees clockwise)
        right_angle = angle + math.pi / 2
        offset = 6.0  # pixels to offset to the right

        offset_pos = (
            base_pos[0] + math.cos(right_angle) * offset,
            base_pos[1] + math.sin(right_angle) * offset
        )

        return offset_pos

    def vehicle_angle(self, v: Vehicle) -> float:
        na = self.nodes.get(v.current_node_id)
        nb = self.nodes.get(v.next_node_id)
        if not na or not nb:
            return 0.0
        return angle_of(na.pos, nb.pos)
