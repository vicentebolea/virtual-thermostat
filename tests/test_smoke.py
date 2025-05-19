import subprocess
import sys


def test_help_command():
    """Test that the --help command works."""
    result = subprocess.run(
        [sys.executable, "-m", "virtual_thermostat.main", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Virtual Thermostat" in result.stdout
    assert "--host" in result.stdout
    assert "--zipcode" in result.stdout