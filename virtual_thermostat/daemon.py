#!/usr/bin/env python3
"""
Virtual Thermostat Daemon
Continuously runs the thermostat CLI app at specified intervals.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("thermostat-daemon")


class ThermostatDaemon:
    def __init__(self, interval=60, config_file=None, state_file=None, temp_file=None):
        self.interval = interval
        self.running = True
        self.main_script_path = Path(__file__).parent / "cli.py"
        self.config_file = config_file
        self.state_file = state_file
        self.temp_file = temp_file

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    async def run_thermostat_cli(self):
        """Run the thermostat CLI script as a subprocess."""
        try:
            logger.info("Running thermostat CLI...")

            # Build command arguments
            cmd = [sys.executable, str(self.main_script_path)]
            if self.config_file:
                cmd.extend(["--config", self.config_file])
            if self.state_file:
                cmd.extend(["--state", self.state_file])
            if self.temp_file:
                cmd.extend(["--temp", self.temp_file])

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info("Thermostat CLI completed successfully")
                if stdout:
                    logger.debug(f"CLI output: {stdout.decode().strip()}")
            else:
                logger.error(
                    f"Thermostat CLI failed with return code {process.returncode}"
                )
                if stderr:
                    logger.error(f"CLI error: {stderr.decode().strip()}")

            return process.returncode == 0

        except Exception as e:
            logger.error(f"Error running thermostat CLI: {e}")
            return False

    async def run(self):
        """Main daemon loop."""
        logger.info(f"Starting thermostat daemon with {self.interval}s interval")

        while self.running:
            try:
                # Simply run the CLI - it handles all logic internally
                success = await self.run_thermostat_cli()
                if not success:
                    logger.warning("Thermostat CLI run failed")

                # Wait for next interval
                if self.running:
                    logger.debug(f"Waiting {self.interval}s until next run...")
                    await asyncio.sleep(self.interval)

            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in daemon loop: {e}")
                if self.running:
                    await asyncio.sleep(self.interval)

        logger.info("Daemon stopped")


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Virtual Thermostat Daemon")
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=60,
        help="Interval between thermostat runs in seconds (default: 60)",
    )
    parser.add_argument(
        "--config",
        help="Path to config file",
    )
    parser.add_argument(
        "--state",
        help="Path to state file",
    )
    parser.add_argument(
        "--temp",
        help="Path to temperature file",
    )

    args = parser.parse_args()

    async def run_daemon():
        daemon = ThermostatDaemon(
            interval=args.interval,
            config_file=args.config,
            state_file=args.state,
            temp_file=args.temp,
        )
        await daemon.run()

    try:
        asyncio.run(run_daemon())
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")
    except Exception as e:
        logger.error(f"Daemon error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
