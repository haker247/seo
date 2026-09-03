"""Локальная проверка доступов + dry-run утреннего дайджеста. Секреты в stdout не пишет."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
PYTHON = sys.executable

DOMAIN = "xn--b1adafaol8cdkl0m.xn--p1acf"

UPSERT = (
    "CURSOR_API_KEY",
    "CURSOR_MODEL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "SEO_SITE_DOMAIN",
    "GSC_SITE_URL",
    "M2_SITE_ROOT",
    "YANDEX_WEBMASTER_TOKEN",
    "PSI_API_KEY",
    "GSC_OAUTH_CLIENT_ID",
    "GSC_OAUTH_CLIENT_SECRET",
    "GSC_OAUTH_REFRESH_TOKEN",
)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, val = s.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


def upsert_env(path: Path) -> None:
    os.environ.setdefault("SEO_SITE_DOMAIN", DOMAIN)
    os.environ.setdefault("GSC_SITE_URL", f"sc-domain:{DOMAIN}")
    os.environ.setdefault("M2_SITE_ROOT", f"https://{DOMAIN}")
    os.environ.setdefault("CURSOR_MODEL", "composer-2.5")

    existing: list[str] = []
    if path.exists():
        existing = path.read_text(encoding="utf-8").splitlines()
    keep = [
        ln for ln in existing
        if not any(ln.startswith(k + "=") for k in UPSERT)
    ]
    keep.append("")
    for key in UPSERT:
        val = os.environ.get(key, "").strip()
        if val:
            keep.append(f"{key}={val}")
    path.write_text("\n".join(keep).rstrip() + "\n", encoding="utf-8")


def run_step(name: str, args: list[str]) -> bool:
    print(f"\n===== {name} =====", flush=True)
    proc = subprocess.run(args, cwd=ROOT, env=os.environ.copy())
    ok = proc.returncode == 0
    print(f"----- {name}: {'OK' if ok else 'FAIL'} (exit {proc.returncode}) -----", flush=True)
    return ok


def main() -> int:
    load_env(ENV_PATH)
    upsert_env(ENV_PATH)
    load_env(ENV_PATH)

    missing = [
        k for k in (
            "GSC_OAUTH_REFRESH_TOKEN",
            "GSC_OAUTH_CLIENT_ID",
            "GSC_OAUTH_CLIENT_SECRET",
            "YANDEX_WEBMASTER_TOKEN",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
        )
        if not os.environ.get(k, "").strip()
    ]
    if missing:
        print("Нет переменных:", ", ".join(missing))
        return 2

    results = [
        run_step("GSC", [PYTHON, str(ROOT / "modules" / "gsc_client.py")]),
        run_step("Yandex Webmaster", [PYTHON, str(ROOT / "modules" / "yandex_webmaster.py")]),
        run_step("Telegram", [PYTHON, str(ROOT / "notifiers" / "telegram.py")]),
        run_step("Daily digest dry-run", [PYTHON, str(ROOT / "orchestrator.py"), "daily", "--dry-run"]),
    ]
    print("\n===== SUMMARY =====")
    names = ["GSC", "Yandex Webmaster", "Telegram", "Daily digest dry-run"]
    for name, ok in zip(names, results):
        print(f"  {'OK  ' if ok else 'FAIL'} {name}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
