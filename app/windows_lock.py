"""Small fcntl.flock-compatible adapter for Windows file locks."""
import msvcrt
import time

LOCK_EX = 1
LOCK_NB = 2


def flock(stream, operation):
    stream.seek(0)
    try:
        stream.write("0")
        stream.flush()
    except (OSError, ValueError):
        pass
    mode = msvcrt.LK_NBLCK if operation & LOCK_NB else msvcrt.LK_LOCK
    while True:
        try:
            msvcrt.locking(stream.fileno(), mode, 1)
            return
        except OSError:
            if operation & LOCK_NB:
                raise BlockingIOError("lock already held") from None
            time.sleep(0.1)
