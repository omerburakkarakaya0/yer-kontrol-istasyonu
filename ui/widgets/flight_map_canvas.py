"""Full-size map with independent, mouse-safe instrument overlays."""
from PyQt5.QtWidgets import QWidget, QVBoxLayout


class FlightMapCanvas(QWidget):
    def __init__(self, map_widget, parent=None):
        super().__init__(parent)
        self.map_widget = map_widget
        self.panels = ()
        self.setMinimumSize(760, 620)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(map_widget)

    def set_panels(self, telemetry, hud, camera, teams, modes):
        self.panels = (telemetry, hud, camera, teams, modes)
        for panel in self.panels:
            panel.setParent(self)
            panel.show()
            panel.raise_()
        self._position_panels()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_panels()

    def _position_panels(self):
        if not self.panels:
            return
        telemetry, hud, camera, teams, modes = self.panels
        gap = 12
        panel_width = min(360, max(312, int(self.width() * .24)))
        right_x = self.width() - panel_width - gap

        # All three bottom instruments share one height and one baseline.
        instrument_height = max(280, telemetry.minimumSizeHint().height(),
                                hud.minimumSizeHint().height(), modes.minimumSizeHint().height())
        hud_minimum = hud.minimumSizeHint().height()
        camera_minimum = max(140, camera.minimumSizeHint().height())
        # The right column now contains the full HUD. Reserve enough height
        # for its readings and a usable camera view at the smallest window size.
        self.setMinimumHeight(max(620, instrument_height + hud_minimum + camera_minimum + 4 * gap))
        height = self.height() - 2 * gap
        bottom_row_fits = self.width() >= 3 * panel_width + 4 * gap
        if bottom_row_fits:
            telemetry_x = (self.width() - panel_width) // 2
            telemetry_y = self.height() - gap - instrument_height
        else:
            # On a small display the three bottom instruments cannot fit side
            # by side. Move telemetry above the teams instead of overlapping them.
            telemetry_x = min((self.width() - panel_width) // 2,
                              right_x - panel_width - gap)
            telemetry_y = gap
        telemetry.setGeometry(telemetry_x, telemetry_y, panel_width, instrument_height)
        teams.setGeometry(gap, self.height() - gap - instrument_height, panel_width, instrument_height)

        mode_height = instrument_height
        camera_height = min(260, max(190, int(height * .32)),
                            height - mode_height - hud_minimum - 2 * gap)
        hud_height = height - mode_height - camera_height - 2 * gap
        # One aligned right-hand column: camera, HUD, modes.
        modes_y = self.height() - gap - mode_height
        camera.setGeometry(right_x, gap, panel_width, camera_height)
        hud.setGeometry(right_x, 2 * gap + camera_height, panel_width, hud_height)
        modes.setGeometry(right_x, modes_y, panel_width, mode_height)
