"""Capture deadlines and bounded pipe cleanup (not generator inputs).

Windows job objects guarantee full descendant ownership. POSIX process-group
cleanup is best effort: descendants can leave the child's group.
"""
import ctypes
import os
import signal
import subprocess
import sys
import threading
import time

# Local plumbing is minutes; large assemblies/decoders need generous bounds.
GIT_SECONDS = 120
PROBE_SECONDS = 120
ASSEMBLY_SECONDS = 1200
DECODER_SECONDS = 1200
CAPTURE_SECONDS = 14400
WIKI_SECONDS = 15000  # Wiki's 4-hour watchdog plus 10 minutes for its timeout report.
STDERR_LIMIT = 4096
READER_JOIN_SECONDS = 1  # Cleanup grace per pipe, including a blocked consumer.


def windows_job(process):
    """Assign the suspended child before it can create descendants."""
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit", ctypes.c_longlong), ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD), ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", ctypes.c_ulonglong * 6),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        limits = Extended()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        resume = ctypes.WinDLL("ntdll").NtResumeProcess
        resume.argtypes = [wintypes.HANDLE]
        if resume(wintypes.HANDLE(process._handle)):
            raise OSError("Could not resume capture child")
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    return lambda: kernel.CloseHandle(handle)


def run_process(args, *, timeout, check=True, text=True, encoding="utf-8",
                errors="replace", cancel=None, env=None, forward=False):
    """Drain both pipes concurrently, bound stderr, and reap the owned process."""
    started = time.monotonic()
    process = None
    close_job = None
    readers = []
    stdout, stderr = bytearray(), bytearray()
    reason = None

    def drain(pipe, target, limit, destination):
        try:
            while block := pipe.read1(65536):
                if not forward or limit:
                    target.extend(block)
                    if limit:
                        del target[:-limit]
                if forward:
                    destination.buffer.write(block)
                    destination.buffer.flush()
        finally:
            pipe.close()

    try:
        if cancel is not None and cancel.is_set():
            raise RuntimeError("cancelled")
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                                   creationflags=0x4 if os.name == "nt" else 0,
                                   start_new_session=os.name != "nt")
        if os.name == "nt":
            close_job = windows_job(process)
        for pipe, target, limit, destination in ((process.stdout, stdout, None, sys.stdout),
                                                  (process.stderr, stderr, STDERR_LIMIT, sys.stderr)):
            reader = threading.Thread(target=drain, args=(pipe, target, limit, destination), daemon=True)
            reader.start()
            readers.append(reader)
        while True:
            if cancel is not None and cancel.is_set():
                reason = "cancelled"
                break
            if time.monotonic() - started >= timeout:
                reason = "deadline exceeded"
                break
            if process.poll() is not None:
                # Descendants may still own pipes even after their parent exits.
                reason = f"exit {process.returncode}" if check and process.returncode else None
                break
            time.sleep(0.02)
    except BaseException as exc:
        reason = str(exc)
        if not isinstance(exc, Exception):
            raise
    finally:
        if process is not None:
            try:
                if close_job is not None:
                    close_job()
                elif os.name != "nt":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                elif process.poll() is None:
                    process.kill()  # Job setup failed while child was suspended.
            except Exception as exc:
                reason = f"{reason or 'cleanup failed'}; tree cleanup: {exc}"
            finally:
                process.wait()
        for reader in readers:
            reader.join(READER_JOIN_SECONDS)
        if any(reader.is_alive() for reader in readers):
            reason = f"{reason or 'output drain blocked'}; output drain did not finish"
    if reason:
        tail = stderr.decode(encoding, errors=errors)
        raise RuntimeError(f"{os.path.basename(str(args[0]))}: {reason} (deadline {timeout:g}s); stderr tail:\n{tail}")
    return subprocess.CompletedProcess(args, process.returncode,
                                       stdout.decode(encoding, errors) if text else bytes(stdout),
                                       stderr.decode(encoding, errors) if text else bytes(stderr))


if __name__ == "__main__":
    try:
        run_process(sys.argv[2:], timeout=float(sys.argv[1]), forward=True)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
