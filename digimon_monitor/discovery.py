from __future__ import annotations

import csv
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import io
import os
import subprocess
from typing import Iterable


@dataclass(frozen=True, slots=True)
class EmulatorSignature:
    name: str
    process_names: frozenset[str]
    adb_hint: str
    suggested_address: str = ""


@dataclass(frozen=True, slots=True)
class RunningEmulator:
    name: str
    matched_processes: tuple[str, ...]
    adb_hint: str
    suggested_address: str = ""


EMULATOR_SIGNATURES = (
    EmulatorSignature(
        name="BlueStacks",
        process_names=frozenset(
            {"hd-player", "bluestacks", "bluestacksappplayer"}
        ),
        adb_hint="设置 → 高级 → 开启“Android 调试(ADB)”，保存并记下端口。",
    ),
    EmulatorSignature(
        name="雷电模拟器 / LDPlayer",
        process_names=frozenset(
            {"dnplayer", "ldplayer", "ldplayer9"}
        ),
        adb_hint="设置 → 其他设置 → ADB 调试 → 开启本地连接。",
    ),
    EmulatorSignature(
        name="夜神模拟器 / NoxPlayer",
        process_names=frozenset({"nox", "noxplayer"}),
        adb_hint="设置中开启 Root/ADB 调试；首个实例通常使用本地 62001 端口。",
        suggested_address="127.0.0.1:62001",
    ),
    EmulatorSignature(
        name="MuMu 模拟器",
        process_names=frozenset(
            {
                "mumuplayer",
                "mumunxmain",
                "nemuplayer",
                "mumuemulator",
            }
        ),
        adb_hint="在问题诊断或多开器中查看 ADB 端口；部分版本使用 7555。",
        suggested_address="127.0.0.1:7555",
    ),
    EmulatorSignature(
        name="逍遥模拟器 / MEmu",
        process_names=frozenset({"memu", "memuconsole"}),
        adb_hint="启动模拟器并开启 ADB；首个实例常见本地端口为 21503。",
        suggested_address="127.0.0.1:21503",
    ),
    EmulatorSignature(
        name="Genymotion",
        process_names=frozenset(
            {"genymotion", "genymotion-player"}
        ),
        adb_hint="在 Android SDK 设置中选择使用本机 SDK，然后刷新 ADB。",
    ),
)


def _normalize_process_name(name: str) -> str:
    normalized = name.strip().lower()
    return normalized[:-4] if normalized.endswith(".exe") else normalized


def _toolhelp_process_names() -> set[str]:
    if os.name != "nt":
        return set()

    class ProcessEntry32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_snapshot = kernel32.CreateToolhelp32Snapshot
    create_snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    create_snapshot.restype = wintypes.HANDLE
    process_first = kernel32.Process32FirstW
    process_first.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessEntry32W),
    ]
    process_first.restype = wintypes.BOOL
    process_next = kernel32.Process32NextW
    process_next.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessEntry32W),
    ]
    process_next.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    snapshot = create_snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    invalid_handle = ctypes.c_void_p(-1).value
    if snapshot in (None, invalid_handle):
        return set()

    names: set[str] = set()
    entry = ProcessEntry32W()
    entry.dwSize = ctypes.sizeof(ProcessEntry32W)
    try:
        if process_first(snapshot, ctypes.byref(entry)):
            while True:
                names.add(_normalize_process_name(entry.szExeFile))
                if not process_next(snapshot, ctypes.byref(entry)):
                    break
    finally:
        close_handle(snapshot)
    return names


def _powershell_process_names() -> set[str]:
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-Process | Select-Object -ExpandProperty ProcessName",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return set()
    if result.returncode != 0:
        return set()
    return {
        _normalize_process_name(line)
        for line in result.stdout.splitlines()
        if line.strip()
    }


def running_process_names() -> set[str]:
    native_names = _toolhelp_process_names()
    if native_names:
        return native_names
    try:
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return set()
    if result.returncode != 0:
        return _powershell_process_names()
    names: set[str] = set()
    for row in csv.reader(io.StringIO(result.stdout)):
        if row:
            names.add(_normalize_process_name(row[0]))
    return names or _powershell_process_names()


def detect_running_emulators(
    process_names: Iterable[str] | None = None,
) -> list[RunningEmulator]:
    running = {
        _normalize_process_name(name)
        for name in (
            process_names if process_names is not None else running_process_names()
        )
    }
    detected: list[RunningEmulator] = []
    for signature in EMULATOR_SIGNATURES:
        matches = tuple(sorted(running & signature.process_names))
        if matches:
            detected.append(
                RunningEmulator(
                    name=signature.name,
                    matched_processes=matches,
                    adb_hint=signature.adb_hint,
                    suggested_address=signature.suggested_address,
                )
            )
    return detected
