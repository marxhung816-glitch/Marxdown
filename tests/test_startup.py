import os
from pathlib import Path
import subprocess
import sys


PROJECT = Path(__file__).resolve().parent.parent


def test_importing_main_window_does_not_load_webengine():
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(
        [sys.executable, "-c", "import sys; import app.main_window; print('PySide6.QtWebEngineWidgets' in sys.modules)"],
        cwd=PROJECT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert result.stdout.strip() == "False"


def test_open_file_stays_responsive_while_webengine_imports(tmp_path: Path):
    source = tmp_path / "首次打开.md"
    source.write_text("# 首次打开", encoding="utf-8")
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    script = """
import builtins, json, sys, time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow
original_import = builtins.__import__
def delayed_import(name, *args, **kwargs):
    if name == 'tab_manager' or name.endswith('.tab_manager'):
        time.sleep(0.7)
    return original_import(name, *args, **kwargs)
builtins.__import__ = delayed_import
app = QApplication([])
window = MainWindow()
window.show()
start = time.perf_counter()
accepted = window.open_file(sys.argv[1])
elapsed = time.perf_counter() - start
def check():
    if window.current_document() is not None:
        app.quit()
    else:
        QTimer.singleShot(50, check)
QTimer.singleShot(50, check)
QTimer.singleShot(5000, app.quit)
app.exec()
print(json.dumps({'accepted': accepted, 'elapsed': elapsed, 'opened': window.current_document() is not None}))
window.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(source)],
        cwd=PROJECT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    import json
    outcome = json.loads(result.stdout.strip())
    assert outcome["accepted"]
    assert outcome["elapsed"] < 0.4
    assert outcome["opened"]
