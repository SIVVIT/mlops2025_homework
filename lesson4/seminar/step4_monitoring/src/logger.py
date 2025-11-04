import json
import time
from pathlib import Path
from typing import Any

try:
    from colorama import Fore, Style
    from colorama import init as colorama_init

    colorama_init()
    _HAS_COLOR = True
except Exception:
    _HAS_COLOR = False

    class Dummy:
        RESET_ALL = ""
        RED = ""
        YELLOW = ""
        GREEN = ""

    Fore = Style = Dummy()


class JsonLogger:
    def __init__(self, log_file: str, console_colors: bool = True):
        self.log_path = Path(log_file)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.console_colors = console_colors and _HAS_COLOR
        self._fp = self.log_path.open("a", encoding="utf-8")

    def _ts(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())

    def _console(self, level: str, msg: str):
        if not self.console_colors:
            print(f"[{level}] {msg}")
            return
        color = {
            "INFO": Fore.GREEN,
            "WARN": Fore.YELLOW,
            "ERROR": Fore.RED,
        }.get(level, "")
        reset = Style.RESET_ALL if self.console_colors else ""
        print(f"{color}[{level}] {msg}{reset}")

    def log(self, level: str, message: str, **kwargs: Any):
        rec = {"ts": self._ts(), "level": level, "message": message}
        if kwargs:
            rec.update(kwargs)
        self._fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._fp.flush()
        self._console(level, f"{message} | {kwargs}" if kwargs else message)

    def info(self, message: str, **kwargs: Any):
        self.log("INFO", message, **kwargs)

    def warn(self, message: str, **kwargs: Any):
        self.log("WARN", message, **kwargs)

    def error(self, message: str, **kwargs: Any):
        self.log("ERROR", message, **kwargs)

    def close(self):
        try:
            self._fp.close()
        except Exception:
            pass
