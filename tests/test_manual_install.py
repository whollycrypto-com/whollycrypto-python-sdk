import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import whollycrypto


class ManualInstallTests(unittest.TestCase):
    def test_manual_package_and_intact_source_layout_without_site_packages(self):
        for layout in ("copy", "source"):
            with self.subTest(layout=layout), tempfile.TemporaryDirectory(prefix="wholly-python-manual-") as folder:
                app = Path(folder)
                destination = app if layout == "copy" else app / "whollycrypto-python-sdk" / "src"
                shutil.copytree(
                    Path(whollycrypto.__file__).parent,
                    destination / "whollycrypto",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
                shutil.copyfile(Path(__file__).with_name("manual_probe.py"), app / "app.py")
                result = subprocess.run(
                    [sys.executable, "-E", "-S", "-B", str(app / "app.py"), layout],
                    cwd=tempfile.gettempdir(),
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=15,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
