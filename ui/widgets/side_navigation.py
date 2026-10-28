"""Compact right-hand navigation for the main application pages."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QButtonGroup, QFrame, QPushButton, QVBoxLayout, QWidget, QSizePolicy


class SideNavigation(QFrame):
    def __init__(self, tabs, telemetry_readouts, parent=None):
        super().__init__(parent)
        self.setObjectName("sideNavigation")
        self.setFixedWidth(104)
        self.buttons = QButtonGroup(self)
        self.buttons.setExclusive(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 12, 7, 12)
        layout.setSpacing(12)
        self.navigation_section = QWidget()
        self.navigation_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        navigation_layout = QVBoxLayout(self.navigation_section)
        navigation_layout.setContentsMargins(0, 0, 0, 0)
        navigation_layout.setSpacing(8)
        for index in range(tabs.count()):
            button = QPushButton(tabs.tabText(index).replace(" EKRANI", "\nEKRANI"))
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(40)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            button.setToolTip(tabs.tabText(index))
            self.buttons.addButton(button, index)
            navigation_layout.addWidget(button, 1)
        self.telemetry_section = telemetry_readouts
        self.telemetry_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        layout.addWidget(self.navigation_section, 1)
        layout.addWidget(self.telemetry_section, 1)
        self.telemetry_section.show()
        self.buttons.buttonClicked[int].connect(tabs.setCurrentIndex)
        tabs.currentChanged.connect(self._sync_selection)
        self._sync_selection(tabs.currentIndex())
        self.setStyleSheet("""
            QFrame#sideNavigation {
                background: #0b0e0c;
                border-left: 1px solid #2c3b2e;
            }
            QFrame#sideNavigation QPushButton {
                background: #111712; color: #a1af9c;
                border: 1px solid #2c3b2e; border-radius: 7px;
                font-size: 10px; font-weight: 700; padding: 4px;
            }
            QFrame#sideNavigation QPushButton:hover {
                background: #1b2a1e; color: #f0f3eb; border-color: #577b59;
            }
            QFrame#sideNavigation QPushButton:checked {
                background: #124020; color: #f0f3eb;
                border: 1px solid #577b59; border-left: 3px solid #7ea783;
            }
            QFrame#sideNavigation QPushButton:focus {
                border-color: #b4ceac;
            }
        """)

    def _sync_selection(self, index):
        button = self.buttons.button(index)
        if button is not None:
            button.setChecked(True)
