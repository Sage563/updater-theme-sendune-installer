import json
import logging
import os
import shutil
import subprocess
import hashlib
from pathlib import Path

LOG = "/tmp/narchs-feature-installer.log"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s",
                    handlers=[logging.FileHandler(LOG), logging.StreamHandler()])

ROOT = Path.cwd()


def _installed_db_path() -> Path:
    """Return path to the installed-features DB. Use /var/lib when root, else /tmp for testing."""
    if os.geteuid() == 0:
        p = Path('/var/lib/narchs/features_installed.json')
    else:
        p = Path('/tmp/narchs_features_installed.json')
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_installed_db():
    p = _installed_db_path()
    if not p.exists():
        return {"packages": [], "files": {}, "scripts": []}
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        logging.exception("Failed to read installed DB, starting fresh")
        return {"packages": [], "files": {}, "scripts": []}


def save_installed_db(db):
    p = _installed_db_path()
    p.write_text(json.dumps(db, indent=2), encoding='utf-8')


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, check=True):
    logging.info("Running: %s", cmd)
    res = subprocess.run(cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    logging.info("stdout: %s", res.stdout.strip())
    if res.returncode != 0:
        logging.error("stderr: %s", res.stderr.strip())
        if check:
            raise RuntimeError(f"Command failed: {cmd}")
    return res


def read_manifest():
    mfile = ROOT / "manifest.json"
    if not mfile.exists():
        logging.info("manifest.json not found, using defaults.")
        return {}
    return json.loads(mfile.read_text(encoding='utf-8'))


def install_packages(packages):
    if not packages:
        return
    db = load_installed_db()
    already = set(db.get("packages", []))
    to_install = [p for p in packages if p not in already]
    if not to_install:
        logging.info("No new packages to install.")
        return

    pkgline = " ".join(to_install)
    logging.info("Packages to install: %s", pkgline)
    if os.geteuid() == 0:
        logging.info("Running pacman to install packages")
        run(f"pacman -Sy --noconfirm {pkgline}")
        # Record as installed
        db.setdefault("packages", [])
        db["packages"].extend(to_install)
        save_installed_db(db)
    else:
        logging.info("Not running package manager (not root). Skipping actual install.")
        # For testing, still record them to simulate installation
        db.setdefault("packages", [])
        db["packages"].extend(to_install)
        save_installed_db(db)


def copy_files(files):
    db = load_installed_db()
    db_files = db.setdefault("files", {})
    for item in files:
        src = ROOT / item["src"]
        dst = Path(item["dst"])
        logging.info("Copy %s -> %s", src, dst)
        if not src.exists():
            logging.warning("Source file missing: %s", src)
            continue

        src_sha = _sha256(src)
        dst_record = db_files.get(str(dst))
        if dst.exists() and dst_record == src_sha:
            logging.info("Destination %s already up-to-date, skipping.", dst)
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        # record sha
        db_files[str(dst)] = src_sha
        save_installed_db(db)


def run_feature_scripts(scripts):
    db = load_installed_db()
    done = set(db.setdefault("scripts", []))
    for s in scripts:
        if s in done:
            logging.info("Script %s already run, skipping.", s)
            continue
        path = ROOT / s
        if path.exists():
            path.chmod(0o755)
            res = run(str(path), check=False)
            if res.returncode == 0:
                done.add(s)
                db["scripts"] = list(done)
                save_installed_db(db)
            else:
                logging.error("Script %s failed with exit %s", s, res.returncode)
                raise RuntimeError(f"Feature script failed: {s}")
        else:
            logging.warning("Feature script not found: %s", s)