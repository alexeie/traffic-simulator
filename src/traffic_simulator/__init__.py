"""Traffic Simulator — a birds-eye 2D traffic simulation game."""

from traffic_simulator.app import TrafficSimApp


def main() -> None:
    """Entry point called by `traffic-simulator` console script."""
    app = TrafficSimApp()
    app.run()
