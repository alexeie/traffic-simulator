"""UI widgets: sidebar buttons and the traffic-light configuration panel."""

from __future__ import annotations

import math
from typing import Callable, Optional

import pygame

from traffic_simulator.constants import (
    C_ACCENT, C_ACCENT_DIM, C_BG, C_BUTTON, C_BUTTON_ACTIVE, C_BUTTON_HOVER,
    C_LIGHT_GREEN, C_LIGHT_RED, C_LIGHT_YELLOW, C_SIDEBAR, C_TEXT, C_TEXT_DIM,
    SCREEN_H, SCREEN_W, CANVAS_W,
)
from traffic_simulator.world import LightPhase, TrafficLight


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------

class Button:
    def __init__(
        self,
        rect: tuple[int, int, int, int],
        label: str,
        callback: Callable[[], None],
        *,
        toggle: bool = False,
        color: Optional[tuple[int, int, int]] = None,
    ):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.callback = callback
        self.toggle = toggle
        self.active = False
        self.hovered = False
        self.color = color

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if self.active:
            col = C_BUTTON_ACTIVE
        elif self.hovered:
            col = self.color or C_BUTTON_HOVER
        else:
            col = self.color or C_BUTTON
        pygame.draw.rect(surface, col, self.rect, border_radius=6)
        pygame.draw.rect(surface, (255, 255, 255, 30), self.rect, 1, border_radius=6)
        txt = font.render(self.label, True, C_TEXT if not self.active else C_BG)
        surface.blit(txt, txt.get_rect(center=self.rect.center))

    def handle(self, pos: tuple[int, int], click: bool) -> bool:
        self.hovered = self.rect.collidepoint(pos)
        if click and self.hovered:
            if self.toggle:
                self.active = not self.active
            if self.callback:
                self.callback()
            return True
        return False


# ---------------------------------------------------------------------------
# Traffic-light configuration panel (modal overlay)
# ---------------------------------------------------------------------------

_PHASE_COLOR = {
    LightPhase.GREEN: C_LIGHT_GREEN,
    LightPhase.YELLOW: C_LIGHT_YELLOW,
    LightPhase.RED: C_LIGHT_RED,
}


class LightConfigPanel:
    def __init__(self) -> None:
        self.visible = False
        self.light: Optional[TrafficLight] = None
        self.rect = pygame.Rect(CANVAS_W // 2 - 180, SCREEN_H // 2 - 160, 360, 320)
        self._phase_rects: list[pygame.Rect] = []
        self._offset_minus_r = pygame.Rect(0, 0, 0, 0)
        self._offset_plus_r = pygame.Rect(0, 0, 0, 0)
        self._close_r = pygame.Rect(0, 0, 0, 0)

    def open(self, light: TrafficLight) -> None:
        self.light = light
        self.visible = True

    def close(self) -> None:
        self.visible = False
        self.light = None

    # -- drawing --
    def draw(self, surface: pygame.Surface, font: pygame.font.Font, font_sm: pygame.font.Font) -> None:
        if not self.visible or not self.light:
            return

        # dim backdrop
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        surface.blit(overlay, (0, 0))

        # panel
        pygame.draw.rect(surface, C_SIDEBAR, self.rect, border_radius=12)
        pygame.draw.rect(surface, C_ACCENT, self.rect, 2, border_radius=12)

        title = font.render("Traffic Light Config", True, C_ACCENT)
        surface.blit(title, (self.rect.x + 20, self.rect.y + 16))

        y = self.rect.y + 52
        self._phase_rects.clear()
        for i, (phase, dur) in enumerate(self.light.phases):
            r = pygame.Rect(self.rect.x + 20, y, self.rect.w - 40, 36)
            self._phase_rects.append(r)

            col = _PHASE_COLOR[phase]
            pygame.draw.rect(surface, (40, 44, 52), r, border_radius=6)
            pygame.draw.circle(surface, col, (r.x + 18, r.centery), 8)
            lbl = font_sm.render(f"{phase.name}  {dur:.1f}s", True, C_TEXT)
            surface.blit(lbl, (r.x + 36, r.y + 9))

            minus_r = pygame.Rect(r.right - 70, r.y + 4, 28, 28)
            plus_r = pygame.Rect(r.right - 36, r.y + 4, 28, 28)
            for br in (minus_r, plus_r):
                pygame.draw.rect(surface, C_BUTTON, br, border_radius=4)
            surface.blit(
                font_sm.render("-", True, C_TEXT),
                font_sm.render("-", True, C_TEXT).get_rect(center=minus_r.center),
            )
            surface.blit(
                font_sm.render("+", True, C_TEXT),
                font_sm.render("+", True, C_TEXT).get_rect(center=plus_r.center),
            )
            y += 44

        # offset controls
        y += 10
        surface.blit(
            font_sm.render(f"Phase Offset: {self.light.offset:.1f}s", True, C_TEXT_DIM),
            (self.rect.x + 20, y),
        )
        y += 24
        self._offset_minus_r = pygame.Rect(self.rect.x + 20, y, 60, 28)
        self._offset_plus_r = pygame.Rect(self.rect.x + 90, y, 60, 28)
        for br, txt in ((self._offset_minus_r, "- 0.5s"), (self._offset_plus_r, "+ 0.5s")):
            pygame.draw.rect(surface, C_BUTTON, br, border_radius=4)
            surface.blit(
                font_sm.render(txt, True, C_TEXT),
                font_sm.render(txt, True, C_TEXT).get_rect(center=br.center),
            )

        # close button
        y += 44
        self._close_r = pygame.Rect(self.rect.centerx - 50, y, 100, 32)
        pygame.draw.rect(surface, C_ACCENT_DIM, self._close_r, border_radius=6)
        ct = font_sm.render("Close", True, C_TEXT)
        surface.blit(ct, ct.get_rect(center=self._close_r.center))

    # -- click handling --
    def handle_click(self, pos: tuple[int, int]) -> bool:
        """Returns True if the click was consumed by this panel."""
        if not self.visible or not self.light:
            return False
        if not self.rect.collidepoint(pos):
            self.close()
            return True

        for i, r in enumerate(self._phase_rects):
            minus_r = pygame.Rect(r.right - 70, r.y + 4, 28, 28)
            plus_r = pygame.Rect(r.right - 36, r.y + 4, 28, 28)
            if minus_r.collidepoint(pos):
                phase, dur = self.light.phases[i]
                self.light.phases[i] = (phase, max(0.5, dur - 0.5))
                return True
            if plus_r.collidepoint(pos):
                phase, dur = self.light.phases[i]
                self.light.phases[i] = (phase, dur + 0.5)
                return True

        if self._offset_minus_r.collidepoint(pos):
            self.light.offset = max(0, self.light.offset - 0.5)
            return True
        if self._offset_plus_r.collidepoint(pos):
            self.light.offset += 0.5
            return True
        if self._close_r.collidepoint(pos):
            self.close()
            return True
        return True
