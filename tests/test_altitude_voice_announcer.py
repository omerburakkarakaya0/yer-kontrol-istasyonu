import unittest

from PyQt5.QtTextToSpeech import QTextToSpeech

from core.altitude_voice_announcer import AltitudeVoiceAnnouncer


class FakeSpeech:
    def __init__(self):
        self.messages = []
        self.current_state = QTextToSpeech.Ready
        self.stop_count = 0

    def state(self):
        return self.current_state

    def say(self, message):
        self.messages.append(message)

    def stop(self):
        self.stop_count += 1

    def setVolume(self, _volume):
        pass

    def setRate(self, _rate):
        pass

    def availableLocales(self):
        return []

    def locale(self):
        return "en_US"


class AltitudeVoiceAnnouncerTest(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.speech = FakeSpeech()
        self.announcer = AltitudeVoiceAnnouncer(
            speech=self.speech,
            clock=lambda: self.now,
        )
        self.announcer.set_connected(True)

    def test_altitude_bands_have_required_intervals(self):
        cases = [
            (101.0, 5.0),
            (100.0, 3.0),
            (60.1, 3.0),
            (60.0, 2.0),
            (30.0, 2.0),
            (29.9, 1.0),
        ]
        for altitude, expected in cases:
            with self.subTest(altitude=altitude):
                self.assertEqual(self.announcer.interval_for_altitude(altitude), expected)

    def test_announces_immediately_then_uses_band_cadence(self):
        self.assertTrue(self.announcer.update_altitude(120.0))
        self.now = 4.9
        self.assertFalse(self.announcer.update_altitude(119.0))
        self.now = 5.0
        self.assertTrue(self.announcer.update_altitude(118.0))
        self.assertEqual(self.speech.messages, ["İrtifa 120 metre", "İrtifa 118 metre"])

    def test_entering_more_urgent_band_announces_immediately(self):
        self.announcer.update_altitude(120.0)
        self.now = 0.5

        self.assertTrue(self.announcer.update_altitude(25.0))

        self.assertEqual(self.speech.messages[-1], "İrtifa 25 metre")

    def test_busy_speech_does_not_overlap_or_consume_due_warning(self):
        self.announcer.update_altitude(25.0)
        self.now = 1.0
        self.speech.current_state = QTextToSpeech.Speaking
        self.assertFalse(self.announcer.update_altitude(24.0))
        self.speech.current_state = QTextToSpeech.Ready
        self.assertTrue(self.announcer.update_altitude(24.0))
        self.assertEqual(len(self.speech.messages), 2)

    def test_disconnect_stops_and_suppresses_announcements(self):
        self.announcer.set_connected(False)

        self.assertFalse(self.announcer.update_altitude(20.0))
        self.assertEqual(self.speech.messages, [])
        self.assertEqual(self.speech.stop_count, 1)


if __name__ == "__main__":
    unittest.main()
