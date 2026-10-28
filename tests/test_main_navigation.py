import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts"))

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget

from core.mission_manager import MissionManager
from core.shared_map_state import SharedMapState
from main import load_stylesheet
from ui.main_window import MainWindow
from ui.widgets.map_widget import MapWidget
from models.telemetry import TelemetryData


class LayoutOnlyWindow(MainWindow):
    """Build real pages without starting cameras, telemetry, or network workers."""
    def __init__(self):
        QMainWindow.__init__(self)
        self.mission_manager = MissionManager()
        self.shared_map_state = SharedMapState()
        self.init_ui()

    def closeEvent(self, event):
        event.accept()


class MainNavigationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        load_stylesheet(cls.app)

    def setUp(self):
        # Exercise page navigation using the supported 2D analysis fallback;
        # QtWebEngine requires a native GPU window, unavailable offscreen.
        web_patch = patch("ui.tabs.live_analysis_tab.QWebEngineView", None)
        web_patch.start()
        self.addCleanup(web_patch.stop)
        self.window = LayoutOnlyWindow()
        self.window.resize(1900, 1000)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        for map_widget in self.window.findChildren(MapWidget):
            map_widget.map_source.close()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_right_navigation_selects_each_page_and_stays_in_sync(self):
        tabs = self.window.tab_widget
        nav = self.window.side_navigation
        self.assertFalse(tabs.tabBar().isVisible())
        self.assertIsNone(self.window.findChild(QWidget, "topHeader"))
        self.assertLess(tabs.geometry().right(), nav.x())
        self.assertLessEqual(nav.width(), 110)
        self.assertEqual(tabs.y(), 0)
        for index in range(tabs.count()):
            button = nav.buttons.button(index)
            QTest.mouseClick(button, Qt.LeftButton)
            self.assertEqual(tabs.currentIndex(), index)
            self.assertTrue(button.isChecked())
        tabs.setCurrentIndex(0)
        self.assertTrue(nav.buttons.button(0).isChecked())
        button = nav.buttons.button(2)
        button.setFocus()
        QTest.keyClick(button, Qt.Key_Space)
        self.assertIs(tabs.currentWidget(), self.window.logs_tab)

    def test_full_window_keeps_equal_sidebar_and_unobscured_panels(self):
        for width, height in ((1200, 800), (1366, 768), (1920, 1080)):
            self.window.resize(width, height)
            self.app.processEvents()
            flight = self.window.flight_tab
            sidebar = (flight.connection_group, flight.referee_group, flight.flight_logs)
            self.assertLessEqual(max(p.height() for p in sidebar) - min(p.height() for p in sidebar), 1)
            self.assertEqual(sidebar[-1].geometry().bottom() + 1, flight.left_scroll.viewport().height())
            for index, panel in enumerate(flight.map_canvas.panels):
                self.assertTrue(flight.map_canvas.rect().contains(panel.geometry()))
                for other in flight.map_canvas.panels[index + 1:]:
                    self.assertFalse(panel.geometry().intersects(other.geometry()))
            if width == 1920:
                self.assertEqual(flight.telemetry_group.geometry().bottom(), flight.teams_widget.geometry().bottom())

            instruments = (flight.teams_widget, flight.telemetry_group, flight.mode_group)
            self.assertEqual(len({panel.height() for panel in instruments}), 1)
            nav = self.window.side_navigation
            self.assertLessEqual(abs(nav.navigation_section.height() - nav.telemetry_section.height()), 1)
            cards = (flight.card_battery, flight.card_ground_speed, flight.card_air_speed, flight.card_signal)
            self.assertLessEqual(max(c.height() for c in cards) - min(c.height() for c in cards), 1)
            self.assertGreater(flight.aircraft_model_widget.height(), 200)
            self.assertEqual(flight.telemetry_group.layout().count(), 1)
            self.assertEqual(flight.connection_scroll.verticalScrollBar().maximum(), 0)
            # The enlarged connect button now reaches the foot of its card.
            button_bottom = flight.btn_connect.mapTo(flight.connection_group, flight.btn_connect.rect().bottomLeft()).y()
            self.assertLess(flight.connection_group.height() - button_bottom, 20)

    def test_persistent_readouts_update_on_other_pages_without_clipping(self):
        flight = self.window.flight_tab
        self.window.tab_widget.setCurrentWidget(self.window.logs_tab)
        flight.update_telemetry(TelemetryData(connected=True, latitude=38.32185,
            longitude=38.43050, ground_speed=123.45, air_speed=124.56,
            battery_remaining=86))
        self.app.processEvents()
        cards = (flight.card_battery, flight.card_ground_speed, flight.card_air_speed, flight.card_signal)
        self.assertEqual([card.value_label.text() for card in cards],
                         ["86.00%", "123.45 m/s", "124.56 m/s", "100%"])
        for width, height in ((1200, 800), (1920, 1080)):
            self.window.resize(width, height)
            self.app.processEvents()
            for card in cards:
                self.assertTrue(card.isVisible())
                self.assertTrue(self.window.side_navigation.isAncestorOf(card))
                self.assertFalse(flight.telemetry_group.isAncestorOf(card))
                for label in (card.title_label, card.value_label):
                    self.assertGreaterEqual(label.width(), label.fontMetrics().horizontalAdvance(label.text()))
        self.window.tab_widget.setCurrentWidget(flight)
        self.app.processEvents()
        self.assertTrue(all(card.isVisible() for card in cards))


if __name__ == "__main__":
    unittest.main()
