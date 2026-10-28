import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from ui.tabs.parameters_tab import ParametersTab


class ParametersTabTest(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.tab = ParametersTab()
        self.tab.set_parameters([
            {
                "name": "ARSPD_USE",
                "value": 0.0,
                "default": 0.0,
                "type": 6,
                "range": "0 2",
                "count": 1,
            }
        ])

    def tearDown(self):
        self.tab.deleteLater()
        self.app.processEvents()

    def test_only_value_column_is_editable_and_change_is_emitted(self):
        name_item = self.tab.table.item(0, 0)
        value_item = self.tab.table.item(0, 1)
        self.assertFalse(bool(name_item.flags() & Qt.ItemIsEditable))
        self.assertTrue(bool(value_item.flags() & Qt.ItemIsEditable))

        emitted = []
        self.tab.write_requested.connect(emitted.append)
        value_item.setText("1")
        self.app.processEvents()

        self.assertTrue(self.tab.write_btn.isEnabled())
        self.assertEqual(self.tab.pending_changes["ARSPD_USE"]["value"], 1.0)
        self.tab._request_write()

        self.assertEqual(emitted, [[{"name": "ARSPD_USE", "value": 1.0, "type": 6}]])
        self.assertTrue(self.tab._writing)

    def test_out_of_range_value_is_rejected(self):
        value_item = self.tab.table.item(0, 1)
        value_item.setText("3")
        self.app.processEvents()

        self.assertIn("error", self.tab.pending_changes["ARSPD_USE"])
        self.assertFalse(self.tab.write_btn.isEnabled())

    def test_verified_write_clears_modified_state(self):
        value_item = self.tab.table.item(0, 1)
        value_item.setText("2")
        self.app.processEvents()

        self.tab.apply_write_result({
            "written": [{"name": "ARSPD_USE", "value": 2.0, "type": 6}],
            "failed": [],
        })

        self.assertFalse(self.tab.pending_changes)
        self.assertFalse(self.tab.parameters[0]["modified"])
        self.assertEqual(self.tab.parameters[0]["value"], 2.0)
        self.assertFalse(self.tab.write_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
