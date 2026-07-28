from __future__ import annotations

from dataclasses import dataclass
import shutil
import subprocess

import cv2
import numpy as np


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
    def __init__(self, executable: str = "adb", timeout_seconds: float = 12):
        resolved = shutil.which(executable)
        self.executable = resolved or executable
        self.timeout_seconds = timeout_seconds

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
            raise AdbError(
                "找不到 adb。请安装 Android platform-tools，或在 config.yaml 设置 adb.executable。"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"ADB 命令超时：{' '.join(args)}") from exc

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
            raise AdbError("ADB 地址格式应为 127.0.0.1:5555")
        result = self._run(["connect", address])
        message = (result.stdout or result.stderr).strip()
        if result.returncode != 0:
            raise AdbError(message or f"无法连接 {address}")
        return message

    def screenshot(self, serial: str) -> np.ndarray:
        result = self._run(
            ["-s", serial, "exec-out", "screencap", "-p"],
            binary=True,
            timeout=max(self.timeout_seconds, 20),
        )
        if result.returncode != 0:
            error = (result.stderr or b"").decode("utf-8", errors="replace").strip()
            raise AdbError(error or f"{serial} 截图失败")
        array = np.frombuffer(result.stdout, dtype=np.uint8)
        frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if frame is None:
            raise AdbError(f"{serial} 返回了无效截图")
        return frame

    def tap(self, serial: str, x: int, y: int) -> None:
        if x < 0 or y < 0:
            raise AdbError("拒绝负坐标点击")
        result = self._run(
            ["-s", serial, "shell", "input", "tap", str(x), str(y)]
        )
        if result.returncode != 0:
            raise AdbError((result.stderr or result.stdout).strip())
