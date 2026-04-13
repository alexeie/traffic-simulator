"""Data model: road network, traffic lights, vehicles, and simulation logic."""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from traffic_simulator.constants import (
    C_CAR_COLORS, HAZARDOUS_DRIVER_RATIO,
    COLLISION_DETECTION_RADIUS,
    SAFE_FOLLOWING_DISTANCE_NORMAL, SAFE_FOLLOWING_DISTANCE_HAZARDOUS,
    COLLISION_RECOVERY_TIME, COLLISION_IMMUNITY_TIME, EMERGENCY_BLINK_RATE
)

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


class DriverBehavior(Enum):
    NORMAL = auto()
    HAZARDOUS = auto()


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
    planned_route: list[int] = field(default_factory=list)  # upcoming nodes in order
    t: float = 0.0           # 0‥1 progress along current segment
    current_speed: float = 0.0    # current speed in pixels/second
    max_speed: float = 120.0      # maximum speed in pixels/second
    acceleration: float = 80.0    # acceleration in pixels/second²
    color: tuple = field(default_factory=lambda: random.choice(C_CAR_COLORS))
    waiting: bool = False
    alive: bool = True
    behavior: DriverBehavior = DriverBehavior.NORMAL  # driver type
    stop_timer: float = 0.0  # for intermittent hazardous stops
    # Collision system fields
    in_collision: bool = False           # Currently in post-collision recovery
    collision_timer: float = 0.0         # Countdown for recovery duration
    emergency_blink_phase: float = 0.0   # Accumulator for blink animation
    collision_immune: bool = False       # Temporary immunity after recovery
    immunity_timer: float = 0.0          # Countdown for immunity period


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

        # Assign behavior based on HAZARDOUS_DRIVER_RATIO
        behavior = (DriverBehavior.HAZARDOUS
                    if random.random() < HAZARDOUS_DRIVER_RATIO
                    else DriverBehavior.NORMAL)

        # Assign color and performance based on behavior
        if behavior == DriverBehavior.NORMAL:
            color = (70, 160, 220)  # Blue
            max_speed = 120.0
            acceleration = 80.0
        else:  # HAZARDOUS
            color = (220, 70, 70)  # Red
            max_speed = 150.0  # 25% faster
            acceleration = 100.0  # 25% faster acceleration

        v = Vehicle(
            self._new_id(),
            start_node.id,
            next_node_id,
            behavior=behavior,
            color=color,
            max_speed=max_speed,
            acceleration=acceleration
        )
        # Pre-plan the next 2-3 nodes ahead
        self._plan_ahead(v, 3)
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

    def _plan_ahead(self, v: Vehicle, num_nodes: int = 3) -> None:
        """Plan the next few nodes ahead for smoother navigation"""
        # Clear existing plan beyond current next_node
        v.planned_route.clear()

        current = v.next_node_id
        previous = v.current_node_id

        for _ in range(num_nodes):
            next_node = self._pick_random_neighbor(current, exclude=previous)
            if not next_node:
                break
            v.planned_route.append(next_node)
            previous = current
            current = next_node

    def _tick_vehicle(self, v: Vehicle, dt: float) -> None:
        # Handle collision immunity period (after recovery)
        if v.collision_immune:
            v.immunity_timer -= dt
            if v.immunity_timer <= 0:
                v.collision_immune = False
                v.immunity_timer = 0.0

        # Handle collision recovery state
        if v.in_collision:
            v.collision_timer -= dt
            v.emergency_blink_phase += dt
            v.current_speed = 0.0  # Stay stopped
            v.waiting = True       # Show waiting indicator

            if v.collision_timer <= 0:
                # Recovery complete, resume normal driving with immunity
                v.in_collision = False
                v.waiting = False
                v.emergency_blink_phase = 0.0
                v.collision_immune = True
                v.immunity_timer = COLLISION_IMMUNITY_TIME
            return  # Skip normal movement logic during recovery

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

        # Obey traffic lights near the destination node (behavior-dependent)
        should_stop = False
        if seg_id and v.t > 0.7:
            light = self.get_light_at(seg_id, nb.id)
            if light:
                if v.behavior == DriverBehavior.NORMAL:
                    # Normal drivers: obey all lights
                    if light.phase == LightPhase.RED:
                        should_stop = True
                    elif light.phase == LightPhase.YELLOW and v.t > 0.85:
                        should_stop = True
                else:  # HAZARDOUS
                    # Hazardous drivers: always run yellows, 20% chance to run reds
                    if light.phase == LightPhase.RED:
                        should_stop = random.random() > 0.2  # 80% obey, 20% run red
                    # Never stop for yellow lights

        # Determine safe following distance based on driver behavior
        safe_distance = (SAFE_FOLLOWING_DISTANCE_HAZARDOUS
                         if v.behavior == DriverBehavior.HAZARDOUS
                         else SAFE_FOLLOWING_DISTANCE_NORMAL)

        # Check for vehicle ahead and apply collision avoidance
        vehicle_ahead = self._get_vehicle_ahead(v, safe_distance + 20)
        collision_avoidance = False

        if vehicle_ahead:
            other_vehicle, distance = vehicle_ahead

            # Direct collision check (skip if either vehicle is immune)
            if not v.collision_immune and not other_vehicle.collision_immune:
                if self._check_collision(v, other_vehicle):
                    # COLLISION! Both vehicles enter emergency state
                    if not other_vehicle.in_collision:  # Avoid double-trigger
                        v.in_collision = True
                        v.collision_timer = COLLISION_RECOVERY_TIME
                        v.emergency_blink_phase = 0.0
                        other_vehicle.in_collision = True
                        other_vehicle.collision_timer = COLLISION_RECOVERY_TIME
                        other_vehicle.emergency_blink_phase = 0.0
                    return  # Immediate stop, skip rest of tick

            # Collision avoidance: brake based on distance and behavior
            if distance < safe_distance:
                collision_avoidance = True
                v.waiting = True
                # Calculate braking intensity: closer = harder brake
                brake_factor = 1.0 - (distance / safe_distance)  # 0.0 to 1.0
                target_speed = v.current_speed * (1.0 - brake_factor * 0.8)  # Reduce up to 80%

        # Check if approaching a sharp turn (when t > 0.6)
        if not collision_avoidance:  # Only set default if not avoiding collision
            target_speed = v.max_speed
            if v.t > 0.6 and v.planned_route:
                # Look ahead to see what the turn angle will be
                next_node_id = v.planned_route[0]
                next_node = self.nodes.get(next_node_id)
                if next_node:
                    # Calculate turn angle
                    angle_in = angle_of(na.pos, nb.pos)
                    angle_out = angle_of(nb.pos, next_node.pos)
                    turn_angle = abs(angle_out - angle_in)
                    # Normalize to 0-π range
                    if turn_angle > math.pi:
                        turn_angle = 2 * math.pi - turn_angle

                    # Sharp turn if angle > 45 degrees (π/4)
                    if turn_angle > math.pi / 4:
                        # Reduce target speed based on sharpness
                        # 45° turn: 70% speed, 90° turn: 40% speed
                        turn_factor = 1.0 - (turn_angle / math.pi) * 0.6
                        target_speed = v.max_speed * max(0.4, turn_factor)

        # Hazardous drivers: random intermittent stops (0.1% chance per frame when moving)
        if v.behavior == DriverBehavior.HAZARDOUS and v.current_speed > 10:
            if v.stop_timer > 0:
                # Currently in a random stop
                v.stop_timer -= dt
                v.waiting = True
                v.current_speed = max(0, v.current_speed - v.acceleration * dt * 3)  # Brake hard
                if v.stop_timer <= 0:
                    v.waiting = False
                if v.current_speed < 1:
                    return  # Stay stopped during timer
            elif random.random() < 0.001:  # 0.1% chance per frame to randomly stop
                v.stop_timer = random.uniform(0.5, 1.5)  # Stop for 0.5-1.5 seconds
                v.waiting = True

        # Apply acceleration/deceleration
        if should_stop:
            # Decelerate to stop at traffic light
            v.waiting = True
            v.current_speed = max(0, v.current_speed - v.acceleration * dt * 2)  # Brake harder
            if v.current_speed < 1:
                return  # Stopped at light
        elif collision_avoidance:
            # Decelerate for vehicle ahead
            v.current_speed = max(target_speed, v.current_speed - v.acceleration * dt * 1.5)
        elif v.current_speed > target_speed:
            # Decelerate for upcoming turn
            v.waiting = False
            v.current_speed = max(target_speed, v.current_speed - v.acceleration * dt * 1.5)
        else:
            # Accelerate to target speed
            v.waiting = False
            v.current_speed = min(target_speed, v.current_speed + v.acceleration * dt)

        # Move forward based on current speed
        v.t += (v.current_speed * dt) / seg_len

        # When reaching the next node, use planned route
        if v.t >= 1.0:
            v.t = 0.0
            v.current_node_id = v.next_node_id

            # Pop next node from planned route
            if v.planned_route:
                v.next_node_id = v.planned_route.pop(0)
                # Plan further ahead to maintain lookahead buffer
                if len(v.planned_route) < 2:
                    self._plan_ahead(v, 3)
            else:
                # Fallback if plan is empty
                next_node = self._pick_random_neighbor(v.current_node_id, exclude=na.id)
                if not next_node:
                    v.alive = False
                    return
                v.next_node_id = next_node
                self._plan_ahead(v, 3)

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

    def _get_vehicle_ahead(self, v: Vehicle, max_distance: float) -> Optional[tuple[Vehicle, float]]:
        """Find the closest vehicle ahead on the same route within max_distance.
        Returns (vehicle, distance) or None if no vehicle found.
        """
        my_pos = self.vehicle_pos(v)

        # Check vehicles on current segment
        for other in self.vehicles.values():
            if other.id == v.id or not other.alive:
                continue

            # Only check vehicles on same segment traveling same direction
            if other.current_node_id == v.current_node_id and other.next_node_id == v.next_node_id:
                # Same segment, check if ahead (other.t > v.t)
                if other.t > v.t:
                    other_pos = self.vehicle_pos(other)
                    distance = dist(my_pos, other_pos)
                    if distance <= max_distance:
                        return (other, distance)

            # Check vehicles on next segment (if we're near end of current segment)
            if v.t > 0.7 and v.planned_route:
                next_next_node = v.planned_route[0] if v.planned_route else None
                if (other.current_node_id == v.next_node_id and
                    other.next_node_id == next_next_node):
                    # Other is on our next segment
                    other_pos = self.vehicle_pos(other)
                    distance = dist(my_pos, other_pos)
                    if distance <= max_distance:
                        return (other, distance)

        return None

    def _check_collision(self, v1: Vehicle, v2: Vehicle) -> bool:
        """Check if two vehicles are colliding (overlapping bounding circles)."""
        pos1 = self.vehicle_pos(v1)
        pos2 = self.vehicle_pos(v2)
        distance = dist(pos1, pos2)
        return distance < COLLISION_DETECTION_RADIUS

    # -- convenience queries --
    def vehicle_pos(self, v: Vehicle) -> tuple[float, float]:
        na = self.nodes.get(v.current_node_id)
        nb = self.nodes.get(v.next_node_id)
        if not na or not nb:
            return (0.0, 0.0)

        # Use quadratic Bezier curve for smoother turns
        # When near the start (t < 0.3) or end (t > 0.7), apply curve smoothing
        t = v.t
        if t < 0.3:
            # Smooth entry: use previous direction if available
            # For now, just use linear interpolation at start
            base_pos = lerp_pt(na.pos, nb.pos, t)
        elif t > 0.7:
            # Smooth exit towards next node
            base_pos = lerp_pt(na.pos, nb.pos, t)
        else:
            # Middle section: straight line
            base_pos = lerp_pt(na.pos, nb.pos, t)

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

        # Current segment angle
        current_angle = angle_of(na.pos, nb.pos)

        # Smooth steering: interpolate angle at end of segment
        if v.t > 0.85 and v.planned_route:
            # At end of segment, start turning towards next direction (only last 15% of segment)
            next_node_id = v.planned_route[0]
            next_node = self.nodes.get(next_node_id)
            if next_node:
                next_angle = angle_of(nb.pos, next_node.pos)
                # Blend angles based on t (0.85 = full current_angle, 1.0 = full next_angle)
                blend = (v.t - 0.85) / 0.15
                return self._interpolate_angle(current_angle, next_angle, blend)

        return current_angle

    def _interpolate_angle(self, angle1: float, angle2: float, t: float) -> float:
        """Interpolate between two angles, taking the shortest path"""
        # Normalize angles to -π to π
        diff = angle2 - angle1
        while diff > math.pi:
            diff -= 2 * math.pi
        while diff < -math.pi:
            diff += 2 * math.pi
        return angle1 + diff * t
