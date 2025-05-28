import subprocess
import sys


def test_cli_module_imports():
    """Test that the cli module can be imported without errors."""
    result = subprocess.run(
        [sys.executable, "-c", "import virtual_thermostat.cli"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_ui_module_imports():
    """Test that the ui module can be imported without errors."""
    result = subprocess.run(
        [sys.executable, "-c", "import virtual_thermostat.ui"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_daemon_module_imports():
    """Test that the daemon module can be imported without errors."""
    result = subprocess.run(
        [sys.executable, "-c", "import virtual_thermostat.daemon"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
