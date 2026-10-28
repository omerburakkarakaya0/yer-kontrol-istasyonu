"""Referee opponents in a stable, numerically ordered three-column grid."""
import math

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QGridLayout, QLabel, QScrollArea, QWidget, QPushButton, QLayout

from core.referee_telemetry import extract_opponent_positions, _identity


class TeamsWidget(QGroupBox):
    team_selected = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__("TAKIMLAR", parent)
        self.setObjectName("bluePanel")
        self.buttons = {}
        self.positions = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 10, 10)
        layout.setSpacing(6)
        self.summary = QLabel("Hakem verisi bekleniyor")
        self.summary.setStyleSheet("color: #a1af9c; font-size: 11px;")
        layout.addWidget(self.summary)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollBar:vertical { width: 8px; }")
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(0, 0, 4, 0)
        self.grid.setSpacing(6)
        self.grid.setAlignment(Qt.AlignTop)
        self.grid.setSizeConstraint(QLayout.SetMinAndMaxSize)
        for col in range(3):
            self.grid.setColumnStretch(col, 1)
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll, 1)

    @staticmethod
    def _team_id(value):
        text = str(value).strip()
        return str(int(text)) if text.isdigit() else text

    @staticmethod
    def _coordinate(item, keys, limit):
        for key in keys:
            try:
                value = float(item[key])
                if math.isfinite(value) and abs(value) <= limit:
                    return value
            except (KeyError, ValueError, TypeError):
                pass
        return None

    def update_teams(self, payload, own_team=None):
        positions = {}
        own_team = self._team_id(own_team) if own_team is not None else None
        for item in extract_opponent_positions(payload):
            identity = _identity(item)
            if identity is None:
                continue
            team = self._team_id(identity)
            if team == own_team:
                continue
            lat = self._coordinate(item, ("iha_enlem", "ihaEnlem", "enlem", "lat", "latitude"), 90)
            lon = self._coordinate(item, ("iha_boylam", "ihaBoylam", "boylam", "lon", "lng", "longitude"), 180)
            positions[team] = (lat, lon)
        identities = sorted(positions, key=lambda team: (0, int(team)) if team.isdigit() else (1, team.casefold()))
        if identities != list(self.buttons):
            for button in self.buttons.values():
                self.grid.removeWidget(button)
                button.deleteLater()
            self.buttons = {}
            for index, team in enumerate(identities):
                button = QPushButton(f"ID {team}")
                button.setFixedHeight(30)
                button.setStyleSheet("QPushButton { color: #b4ceac; background: #1b2a1e; border: 1px solid #3b5740; border-radius: 5px; padding: 3px; font-size: 11px; } QPushButton:hover { background: #213b28; border-color: #577b59; }")
                button.clicked.connect(lambda checked=False, team=team: self._select(team))
                self.grid.addWidget(button, index // 3, index % 3)
                self.buttons[team] = button
            self.grid.activate()
        self.positions = positions
        for team, button in self.buttons.items():
            lat, lon = positions[team]
            valid = lat is not None and lon is not None
            button.setEnabled(valid)
            button.setToolTip(f"Takım {team} · {lat:.6f}, {lon:.6f}\nHaritada göster" if valid else f"Takım {team} · Konum geçersiz")
        self.summary.setText(f"{len(identities)} rakip takım · Haritada görmek için seç" if identities else "Rakip takım verisi yok")

    def clear_teams(self):
        self.update_teams([])
        self.summary.setText("Hakem bağlantısı bekleniyor")

    def _select(self, team):
        lat, lon = self.positions.get(team, (None, None))
        if lat is not None and lon is not None:
            self.team_selected.emit(lat, lon)
