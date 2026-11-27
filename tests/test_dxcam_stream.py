"""DxcamFrameStream unit tests with a fake dxcam module."""

from __future__ import annotations

import numpy as np

from screen_watch.capture.dxcam_backend import DxcamBackend, DxcamFrameStream


class _FakeCam:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self._n = 0

    def start(self, target_fps: float = 60) -> None:
        self.started = True
        self.target_fps = target_fps

    def stop(self) -> None:
        self.stopped = True

    def get_latest_frame(self):
        self._n += 1
        # BGR
        return np.zeros((4, 6, 3), dtype=np.uint8)

    def grab(self):
        return np.zeros((4, 6, 3), dtype=np.uint8)


class _FakeDxcam:
    def __init__(self) -> None:
        self.last_cam: _FakeCam | None = None

    def create(self, output_idx: int = 0):
        self.last_cam = _FakeCam()
        self.last_output = output_idx
        return self.last_cam


def test_dxcam_frame_stream_start_read_close() -> None:
    fake = _FakeDxcam()
    stream = DxcamFrameStream(fake, display_id=1, target_fps=12)
    assert stream.name == "dxcam:stream"
    assert fake.last_cam is not None
    assert fake.last_cam.started is True
    assert fake.last_cam.target_fps == 12.0
    frame = stream.read()
    assert frame.width == 6
    assert frame.height == 4
    assert frame.backend == "dxcam"
    assert len(frame.rgb) == 6 * 4 * 3
    stream.close()
    assert fake.last_cam.stopped is True


def test_dxcam_backend_open_stream(monkeypatch) -> None:
    fake = _FakeDxcam()

    class _Backend(DxcamBackend):
        def __init__(self) -> None:  # noqa: D107
            self._dxcam = fake
            self._camera = None
            self._stream_fps = 15.0

    backend = _Backend()
    stream = backend.open_stream(2)
    assert stream is not None
    assert stream.name == "dxcam:stream"
    assert fake.last_output == 1  # 1-based display → 0-based output
    stream.close()
