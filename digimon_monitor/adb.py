from __future__ import annotations

from dataclasses import dataclass
import shutil
import subprocess

import cv2
import numpy as np

from .i18n import Translator


class AdbError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdbDevice:
    serial: str
    state: str
    model: str = ""
    product: str = ""
    device: str = ""

    @property
    def is_safe_default(self) -> bool:
        identity = " ".join(
            [self.serial, self.model, self.product, self.device]
        ).lower()
        if any(word in identity for word in ("quest", "oculus", "eureka")):
            return False
        return (
            self.serial.startswith("emulator-")
            or self.serial.startswith("127.0.0.1:")
            or any(
                word in identity
                for word in ("bluestacks", "ldplayer", "leidian", "vbox")
            )
        )

    @property
    def display_name(self) -> str:
        model = self.model.replace("_", " ").strip()
        return f"{model or 'Android device'} · {self.serial}"


class AdbClient:
    def __init__(
        self,
        executable: str = "adb",
        timeout_seconds: float = 12,
        translator: Translator | None = None,
    ):
        resolved = shutil.which(executable)
        self.executable = resolved or executable
        self.timeout_seconds = timeout_seconds
        self.tr = translator or Translator()

    def _run(
        self,
        args: list[str],
        *,
        timeout: float | None = None,
        binary: bool = False,
    ) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [self.executable, *args],
                capture_output=True,
                text=not binary,
                timeout=timeout or self.timeout_seconds,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except FileNotFoundError as exc:
            raise AdbError(self.tr("error.adb_missing")) from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(
                self.tr("error.adb_timeout", command=" ".join(args))
            ) from exc

    def list_devices(self) -> list[AdbDevice]:
        result = self._run(["devices", "-l"])
        if result.returncode != 0:
            raise AdbError((result.stderr or result.stdout).strip())
        devices: list[AdbDevice] = []
        for line in result.stdout.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            values: dict[str, str] = {}
            for part in parts[2:]:
                if ":" in part:
                    key, value = part.split(":", 1)
                    values[key] = value
            devices.append(
                AdbDevice(
                    serial=parts[0],
                    state=parts[1],
                    model=values.get("model", ""),
                    product=values.get("product", ""),
                    device=values.get("device", ""),
                )
            )
        return devices

    def connect(self, address: str) -> str:
        address = address.strip()
        if not address or ":" not in address:
            raise AdbError(self.tr("error.adb_address"))
        result = self._run(["connect", address])
        message = (result.stdout or result.stderr).strip()
        if result.returncode != 0:
            raise AdbError(
                message or self.tr("error.adb_connect", address=address)
            )
        return message

    def screenshot(self, serial: str) -> np.ndarray:
        result = self._run(
            ["-s", serial, "exec-out", "screencap", "-p"],
            binary=True,
            timeout=max(self.timeout_seconds, 20),
        )
        if result.returncode != 0:
            error = (result.stderr or b"").decode("utf-8", errors="replace").strip()
            raise AdbError(
                error or self.tr("error.adb_screenshot", serial=serial)
            )
        array = np.frombuffer(result.stdout, dtype=np.uint8)
        frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if frame is None:
            raise AdbError(
                self.tr("error.adb_invalid_screenshot", serial=serial)
            )
        return frame

    def tap(self, serial: str, x: int, y: int) -> None:
        if x < 0 or y < 0:
            raise AdbError(self.tr("error.adb_negative_tap"))
        result = self._run(
            ["-s", serial, "shell", "input", "tap", str(x), str(y)]
        )
        if result.returncode != 0:
            raise AdbError((result.stderr or result.stdout).strip())
