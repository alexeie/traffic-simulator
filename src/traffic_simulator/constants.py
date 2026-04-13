"""Shared constants: colours, dimensions, layout values."""

# Window layout
SCREEN_W = 1280
SCREEN_H = 800
SIDEBAR_W = 260
CANVAS_W = SCREEN_W - SIDEBAR_W
FPS = 60
GRID_SIZE = 40

# Road / node geometry
NODE_RADIUS = 8
ROAD_WIDTH = 24
CAR_LENGTH = 14
CAR_WIDTH = 8

# Colours  (R, G, B)
C_BG              = (30, 32, 38)
C_CANVAS_BG       = (42, 46, 54)
C_GRID            = (50, 54, 62)
C_SIDEBAR         = (24, 26, 32)
C_TEXT            = (210, 215, 225)
C_TEXT_DIM        = (130, 135, 145)
C_ACCENT          = (80, 180, 255)
C_ACCENT_DIM      = (50, 110, 170)
C_ROAD            = (75, 78, 88)
C_ROAD_LINE       = (180, 185, 50)
C_NODE            = (100, 200, 140)
C_NODE_HOVER      = (140, 240, 180)
C_NODE_SELECTED   = (255, 200, 80)
C_ROUNDABOUT      = (90, 94, 104)
C_ROUNDABOUT_RING = (120, 125, 135)
C_LIGHT_RED       = (220, 50, 50)
C_LIGHT_YELLOW    = (240, 220, 50)
C_LIGHT_GREEN     = (50, 200, 80)
C_BUTTON          = (55, 60, 72)
C_BUTTON_HOVER    = (70, 78, 95)
C_BUTTON_ACTIVE   = (80, 180, 255)
C_DANGER          = (200, 60, 60)

C_CAR_COLORS = [
    (220, 70, 70),  (70, 160, 220), (250, 200, 60),
    (100, 210, 130),(200, 120, 220),(255, 150, 80),
    (180, 180, 200),(255, 255, 255),
]
