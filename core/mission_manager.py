"""
Mission Manager
Rota planlama ve mission yönetimi.
"""
from typing import List, Optional
from PyQt5.QtCore import QObject, pyqtSignal
from models.mission_item import MissionItem, MissionItemType


class MissionManager(QObject):
    mission_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mission_items: List[MissionItem] = []
        self.next_sequence = 0
        self.overlay_markers = []

    def add_item(
        self,
        item_type: MissionItemType,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        altitude: Optional[float] = None,
        speed: Optional[float] = None
    ) -> MissionItem:
        item = MissionItem(
            item_type=item_type,
            sequence=self.next_sequence,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            speed=speed,
        )
        self.mission_items.append(item)
        self.next_sequence += 1
        self.mission_changed.emit()
        return item

    def remove_item(self, sequence: int) -> bool:
        for i, item in enumerate(self.mission_items):
            if item.sequence == sequence:
                self.mission_items.pop(i)
                self._renumber_sequences()
                self.mission_changed.emit()
                return True
        return False

    def update_item(self, sequence: int, **kwargs) -> bool:
        for item in self.mission_items:
            if item.sequence == sequence:
                for key, value in kwargs.items():
                    if hasattr(item, key):
                        setattr(item, key, value)
                self.mission_changed.emit()
                return True
        return False

    def get_item(self, sequence: int) -> Optional[MissionItem]:
        for item in self.mission_items:
            if item.sequence == sequence:
                return item
        return None

    def get_all_items(self) -> List[MissionItem]:
        return self.mission_items.copy()

    def get_map_items(self) -> List[MissionItem]:
        return [
            item for item in self.mission_items
            if item.latitude is not None and item.longitude is not None
        ]

    def get_waypoints(self) -> List[MissionItem]:
        return [
            item for item in self.mission_items
            if item.item_type == MissionItemType.WAYPOINT
            and item.latitude is not None
            and item.longitude is not None
        ]

    def clear_mission(self):
        self.mission_items.clear()
        self.next_sequence = 0
        self.mission_changed.emit()

    def replace_items(self, items: List[MissionItem]):
        self.mission_items = list(items or [])
        self._renumber_sequences()
        self.mission_changed.emit()

    def _renumber_sequences(self):
        for i, item in enumerate(self.mission_items):
            item.sequence = i
        self.next_sequence = len(self.mission_items)

    def set_overlay_markers(self, markers):
        self.overlay_markers = list(markers) if markers else []
        self.mission_changed.emit()

    def get_overlay_markers(self):
        return self.overlay_markers.copy()
