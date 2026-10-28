import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    # Qt's offscreen platform needs an explicit font directory on Windows.
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts"))

from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

from main import load_stylesheet
from core.app_logger import AppLogger
from models.telemetry import TelemetryData
from ui.tabs.flight_tab import FlightTab
from ui.widgets.flight_logs_widget import FlightLogsWidget


class FlightLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        load_stylesheet(cls.app)

    def setUp(self):
        self.logger = AppLogger()
        self.tab = FlightTab(None, logger=self.logger)
        self.tab.resize(1366, 650)
        self.tab.show()
        self.app.processEvents()

    def tearDown(self):
        self.tab.map_widget.map_source.close()
        self.tab.close()
        self.tab.deleteLater()
        self.app.processEvents()

    @staticmethod
    def sample(team):
        return {"takim_numarasi": team, "iha_enlem": 38 + int(team) / 1000,
                "iha_boylam": 38.43}

    def test_resized_panels_do_not_overlap_or_block_map(self):
        for width, height in ((1366, 650), (1900, 870), (1100, 630)):
            self.tab.resize(width, height)
            self.app.processEvents()
            canvas = self.tab.map_canvas
            self.assertEqual(canvas.rect(), self.tab.map_widget.geometry())
            for index, panel in enumerate(canvas.panels):
                self.assertTrue(canvas.rect().contains(panel.geometry()))
                self.assertGreaterEqual(panel.height(), panel.minimumSizeHint().height())
                for other in canvas.panels[index + 1:]:
                    self.assertFalse(panel.geometry().intersects(other.geometry()))
            self.assertIs(canvas.childAt(QPoint(canvas.width() // 2, canvas.height() // 2)), self.tab.map_widget)

            self.assertEqual(self.tab.teams_widget.geometry().bottom(), self.tab.mode_group.geometry().bottom())
            self.assertLess(self.tab.teams_widget.x(), self.tab.telemetry_group.x())
            right_column = (self.tab.camera_group, self.tab.hud_widget, self.tab.mode_group)
            self.assertEqual(len({panel.x() for panel in right_column}), 1)
            self.assertEqual(len({panel.width() for panel in right_column}), 1)
            self.assertLess(right_column[0].geometry().bottom(), right_column[1].y())
            self.assertLess(right_column[1].geometry().bottom(), right_column[2].y())
            self.assertLess(self.tab.telemetry_group.geometry().right(), self.tab.camera_group.x())

    def test_sidebar_logs_fit_below_referee_at_each_size(self):
        for width, height in ((1100, 630), (1366, 650), (1900, 870)):
            self.tab.resize(width, height)
            self.app.processEvents()
            panels = (self.tab.connection_group, self.tab.referee_group, self.tab.flight_logs)
            self.assertEqual(len({panel.width() for panel in panels}), 1)
            self.assertEqual(len({panel.x() for panel in panels}), 1)
            self.assertLessEqual(max(panel.height() for panel in panels) - min(panel.height() for panel in panels), 1)
            for upper, lower in zip(panels, panels[1:]):
                self.assertLess(upper.geometry().bottom(), lower.y())
                self.assertLessEqual(lower.y() - upper.geometry().bottom(), 8)
            self.assertEqual(self.tab.left_scroll.verticalScrollBar().maximum(), 0)
            self.assertEqual(panels[-1].geometry().bottom() + 1, self.tab.left_scroll.viewport().height())

    def test_live_log_history_is_bounded_literal_and_cleared(self):
        self.logger.info("<b>Connection ready</b>")
        self.assertIn("<b>Connection ready</b>", self.tab.flight_logs.log_view.toPlainText())
        history = FlightLogsWidget(self.logger)
        self.assertIn("Connection ready", history.log_view.toPlainText())
        for number in range(210):
            self.logger.info(f"Packet {number}")
        self.assertLessEqual(self.tab.flight_logs.log_view.document().blockCount(), 200)
        self.assertIn("Packet 209", self.tab.flight_logs.log_view.toPlainText())
        self.logger.clear()
        self.assertEqual(self.tab.flight_logs.log_view.toPlainText(), "")
        self.assertEqual(history.log_view.toPlainText(), "")
        history.deleteLater()

    def test_thirty_teams_sort_deduplicate_scroll_and_focus(self):
        self.tab.ref_team.setText("99")
        self.tab.set_referee_status(True)
        payload = {"konumBilgileri": [self.sample(i) for i in range(30, 0, -1)] +
                   [self.sample(1), self.sample(99)]}
        self.tab.update_referee_teams(payload)
        self.app.processEvents()
        teams = self.tab.teams_widget
        self.assertEqual(list(teams.buttons), [str(i) for i in range(1, 31)])
        for index, button in enumerate(teams.buttons.values()):
            self.assertEqual(teams.grid.getItemPosition(teams.grid.indexOf(button))[:2], (index // 3, index % 3))
        self.assertGreater(teams.scroll.verticalScrollBar().maximum(), 0)
        teams.buttons["30"].click()
        self.assertAlmostEqual(self.tab.map_widget.center_lat, 38.03)
        self.tab.set_referee_status(False)
        self.tab.update_referee_teams(payload)
        self.assertFalse(teams.buttons)

    def test_invalid_coordinates_and_replaced_snapshot(self):
        teams = self.tab.teams_widget
        teams.update_teams({"takimlar": {"team_2": {"lat": "NaN", "lon": 38},
                                          "team_10": {"lat": 38, "lon": 39}}})
        self.assertEqual(list(teams.buttons), ["2", "10"])
        self.assertFalse(teams.buttons["2"].isEnabled())
        teams.update_teams([self.sample(10)])
        self.assertEqual(list(teams.buttons), ["10"])
        teams.update_teams([])
        self.assertFalse(teams.buttons)

    def test_live_values_and_camera_frame_fit_compact_panels(self):
        self.tab.update_telemetry(TelemetryData(connected=True, latitude=38.32185,
            longitude=38.43050, absolute_altitude=1234, ground_speed=123.45,
            air_speed=124.56, battery_remaining=98, pitch=12, roll=-18, yaw=123))
        self.tab.video_widget.update_frame(QImage(1920, 1080, QImage.Format_RGB32))
        self.app.processEvents()
        self.assertEqual(self.tab.card_ground_speed.value_label.text(), "123.45 m/s")
        self.assertIn("38.321850", self.tab.hud_widget.gps_lat_card.value_label.text())
        for label in (self.tab.card_ground_speed.value_label, self.tab.hud_widget.gps_lat_card.value_label):
            self.assertGreaterEqual(label.width(), label.fontMetrics().horizontalAdvance(label.text()))
        frame = self.tab.video_widget.image_label.pixmap()
        self.assertLessEqual(frame.width(), self.tab.video_widget.image_label.width())
        self.assertLessEqual(frame.height(), self.tab.video_widget.image_label.height())


if __name__ == "__main__":
    unittest.main()
