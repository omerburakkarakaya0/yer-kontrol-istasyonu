from __future__ import annotations

import math
import os
import time

from PyQt5.QtCore import QObject, QLocale, QProcess, QProcessEnvironment
from PyQt5.QtTextToSpeech import QTextToSpeech


class WindowsTurkishSpeech(QObject):
    """Small QTextToSpeech-compatible adapter for Windows OneCore voices."""

    _SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime] > $null
[Windows.Media.Playback.MediaPlayer, Windows.Media.Playback, ContentType=WindowsRuntime] > $null
[Windows.Media.Core.MediaSource, Windows.Media.Core, ContentType=WindowsRuntime] > $null
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices |
    Where-Object { $_.Language -like 'tr-*' } | Select-Object -First 1
if ($null -eq $voice) { exit 2 }
$synth = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::new()
$synth.Voice = $voice
$operation = $synth.SynthesizeTextToStreamAsync($env:BLACKBOX_TTS_TEXT)
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 } |
    Select-Object -First 1
$task = $asTask.MakeGenericMethod([Windows.Media.SpeechSynthesis.SpeechSynthesisStream]).Invoke($null, @($operation))
$stream = $task.GetAwaiter().GetResult()
$player = [Windows.Media.Playback.MediaPlayer]::new()
$player.Source = [Windows.Media.Core.MediaSource]::CreateFromStream($stream, $stream.ContentType)
$player.Play()
$started = $false
$deadline = [DateTime]::UtcNow.AddSeconds(10)
do {
    Start-Sleep -Milliseconds 25
    $state = $player.PlaybackSession.PlaybackState.ToString()
    if ($state -eq 'Playing') { $started = $true }
} while ([DateTime]::UtcNow -lt $deadline -and (-not $started -or $state -in @('Opening', 'Buffering', 'Playing')))
$player.Dispose()
$stream.Dispose()
$synth.Dispose()
"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = QProcess(self)

    @staticmethod
    def is_available() -> bool:
        if os.name != "nt":
            return False
        try:
            import winreg

            root = r"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root) as key:
                index = 0
                while True:
                    try:
                        token = winreg.EnumKey(key, index)
                        index += 1
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(key, token + r"\Attributes") as attrs:
                            language, _ = winreg.QueryValueEx(attrs, "Language")
                        if str(language).lower() in {"041f", "tr-tr", "tr_tr"}:
                            return True
                    except OSError:
                        continue
        except (OSError, ImportError):
            pass
        return False

    def state(self):
        return QTextToSpeech.Ready if self._process.state() == QProcess.NotRunning else QTextToSpeech.Speaking

    def say(self, text):
        if self._process.state() != QProcess.NotRunning:
            return
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("BLACKBOX_TTS_TEXT", str(text))
        self._process.setProcessEnvironment(environment)
        self._process.start(
            "powershell.exe",
            ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command", self._SCRIPT],
        )

    def stop(self):
        if self._process.state() != QProcess.NotRunning:
            self._process.kill()
            self._process.waitForFinished(500)

    def setVolume(self, _volume):
        pass

    def setRate(self, _rate):
        pass

    def availableLocales(self):
        return [QLocale("tr_TR")]

    def setLocale(self, _locale):
        pass

    def locale(self):
        return QLocale("tr_TR")


class AltitudeVoiceAnnouncer(QObject):
    """Announce live altitude with a cadence that increases near the ground."""

    def __init__(self, logger=None, speech=None, clock=None, enabled=True, parent=None):
        super().__init__(parent)
        self.logger = logger
        self.enabled = bool(enabled)
        self._clock = clock or time.monotonic
        if speech is not None:
            self._speech = speech
        elif WindowsTurkishSpeech.is_available():
            self._speech = WindowsTurkishSpeech(self)
        else:
            self._speech = QTextToSpeech("sapi", self)
        self._connected = False
        self._last_spoken_at = None
        self._last_announced_interval = None
        self._configure_voice()

    @staticmethod
    def interval_for_altitude(altitude_m: float) -> float:
        altitude_m = float(altitude_m)
        if altitude_m > 100.0:
            return 5.0
        if altitude_m > 60.0:
            return 3.0
        if altitude_m >= 30.0:
            return 2.0
        return 1.0

    def set_connected(self, connected: bool):
        connected = bool(connected)
        if connected == self._connected:
            return
        self._connected = connected
        self._last_spoken_at = None
        self._last_announced_interval = None
        if not connected:
            self._speech.stop()

    def update_altitude(self, altitude_m) -> bool:
        if not self.enabled or not self._connected:
            return False
        try:
            altitude_m = float(altitude_m)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(altitude_m):
            return False

        interval = self.interval_for_altitude(altitude_m)
        now = self._clock()
        more_urgent_band = (
            self._last_announced_interval is not None
            and interval < self._last_announced_interval
        )
        due = (
            self._last_spoken_at is None
            or now - self._last_spoken_at >= interval
            or more_urgent_band
        )
        if not due or self._speech.state() != QTextToSpeech.Ready:
            return False

        self._speech.say(self._announcement_text(altitude_m))
        self._last_spoken_at = now
        self._last_announced_interval = interval
        return True

    def stop(self):
        self._connected = False
        self._speech.stop()

    def _configure_voice(self):
        if hasattr(self._speech, "setVolume"):
            self._speech.setVolume(1.0)
        if hasattr(self._speech, "setRate"):
            self._speech.setRate(0.0)

        if not hasattr(self._speech, "availableLocales"):
            return
        turkish = next(
            (locale for locale in self._speech.availableLocales() if locale.name().lower().startswith("tr")),
            None,
        )
        if turkish is not None:
            self._speech.setLocale(turkish)

            if hasattr(self._speech, "availableVoices") and hasattr(self._speech, "setVoice"):
                voices = self._speech.availableVoices()
                if voices:
                    self._speech.setVoice(voices[0])

    def _announcement_text(self, altitude_m: float) -> str:
        rounded = max(0, int(round(altitude_m)))
        return f"İrtifa {rounded} metre"
