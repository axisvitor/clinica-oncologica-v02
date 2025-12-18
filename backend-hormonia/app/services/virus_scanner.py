"""
Virus Scanner Service using ClamAV

Provides malware scanning functionality for uploaded files with support for:
- ClamAV daemon integration (clamd)
- Fallback to clamdscan command-line
- Configurable scanning options
- Comprehensive logging and error handling
- Health check capabilities

Environment Variables:
    CLAMAV_ENABLED: Enable/disable virus scanning (default: True in production)
    CLAMAV_HOST: ClamAV daemon host (default: localhost)
    CLAMAV_PORT: ClamAV daemon port (default: 3310)
    CLAMAV_TIMEOUT: Scan timeout in seconds (default: 30)
    CLAMAV_FALLBACK_CLI: Use clamdscan if daemon unavailable (default: True)
"""

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Virus scan result"""

    clean: bool
    threat_found: Optional[str] = None
    scan_time_ms: float = 0.0
    scanner_used: str = "none"
    error: Optional[str] = None


class VirusScannerService:
    """
    Virus scanner service using ClamAV

    Usage:
        scanner = VirusScannerService()
        result = await scanner.scan_file("/path/to/file.pdf")
        if not result.clean:
            logger.error(f"Virus found: {result.threat_found}")
    """

    def __init__(
        self,
        enabled: bool = None,
        host: str = "localhost",
        port: int = 3310,
        timeout: int = 30,
        fallback_cli: bool = True,
    ):
        """
        Initialize virus scanner

        Args:
            enabled: Enable scanning (defaults to True in production)
            host: ClamAV daemon host
            port: ClamAV daemon port
            timeout: Scan timeout in seconds
            fallback_cli: Use CLI if daemon unavailable
        """
        self.enabled = enabled if enabled is not None else self._should_enable()
        self.host = host
        self.port = port
        self.timeout = timeout
        self.fallback_cli = fallback_cli

        # Try to connect to daemon
        self._clamd_available = False
        if self.enabled:
            self._check_clamd_connection()

    def _should_enable(self) -> bool:
        """Determine if scanning should be enabled"""
        env = os.getenv("ENVIRONMENT", "development")
        enabled_env = os.getenv(
            "CLAMAV_ENABLED", "true" if env == "production" else "false"
        )
        return enabled_env.lower() in ("true", "1", "yes")

    def _check_clamd_connection(self) -> bool:
        """Check if ClamAV daemon is available"""
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            self._clamd_available = result == 0

            if self._clamd_available:
                logger.info(f"ClamAV daemon available at {self.host}:{self.port}")
            else:
                logger.warning(
                    f"ClamAV daemon not available at {self.host}:{self.port}"
                )

            return self._clamd_available
        except Exception as e:
            logger.warning(f"Failed to check ClamAV daemon: {e}")
            self._clamd_available = False
            return False

    async def scan_file(self, file_path: str | Path) -> ScanResult:
        """
        Scan a file for viruses

        Args:
            file_path: Path to file to scan

        Returns:
            ScanResult with scan details
        """
        file_path = Path(file_path)

        # Check if scanning is enabled
        if not self.enabled:
            logger.debug(f"Virus scanning disabled, skipping: {file_path}")
            return ScanResult(clean=True, scanner_used="disabled", scan_time_ms=0.0)

        # Check file exists
        if not file_path.exists():
            return ScanResult(
                clean=False, error=f"File not found: {file_path}", scanner_used="none"
            )

        # Try daemon first
        if self._clamd_available:
            result = await self._scan_with_daemon(file_path)
            if result.error is None:
                return result
            logger.warning(f"Daemon scan failed, trying fallback: {result.error}")

        # Fallback to CLI
        if self.fallback_cli:
            return await self._scan_with_cli(file_path)

        # No scanner available
        logger.error("No virus scanner available (daemon down, CLI disabled)")
        return ScanResult(
            clean=True,  # Fail open for availability
            error="No scanner available",
            scanner_used="none",
        )

    async def _scan_with_daemon(self, file_path: Path) -> ScanResult:
        """Scan using ClamAV daemon (pyclamd)"""
        import time

        start = time.time()

        try:
            import pyclamd

            # Connect to daemon
            cd = pyclamd.ClamdNetworkSocket(
                host=self.host, port=self.port, timeout=self.timeout
            )

            # Ping to verify connection
            if not cd.ping():
                return ScanResult(
                    clean=False,
                    error="ClamAV daemon not responding to ping",
                    scanner_used="clamd",
                )

            # Scan file
            result = cd.scan_file(str(file_path))
            scan_time = (time.time() - start) * 1000

            if result is None:
                # Clean file
                return ScanResult(
                    clean=True, scanner_used="clamd", scan_time_ms=scan_time
                )
            else:
                # Threat found
                threat = (
                    result[str(file_path)][1]
                    if str(file_path) in result
                    else "Unknown threat"
                )
                return ScanResult(
                    clean=False,
                    threat_found=threat,
                    scanner_used="clamd",
                    scan_time_ms=scan_time,
                )

        except ImportError:
            logger.warning("pyclamd not installed, cannot use daemon")
            return ScanResult(
                clean=False, error="pyclamd not installed", scanner_used="clamd"
            )
        except Exception as e:
            logger.error(f"Daemon scan error: {e}", exc_info=True)
            return ScanResult(clean=False, error=str(e), scanner_used="clamd")

    async def _scan_with_cli(self, file_path: Path) -> ScanResult:
        """Scan using clamdscan command-line tool"""
        import time

        start = time.time()

        try:
            # Run clamdscan command
            result = subprocess.run(
                ["clamdscan", "--no-summary", str(file_path)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            scan_time = (time.time() - start) * 1000

            # Exit code 0 = clean, 1 = infected, 2+ = error
            if result.returncode == 0:
                return ScanResult(
                    clean=True, scanner_used="clamdscan", scan_time_ms=scan_time
                )
            elif result.returncode == 1:
                # Parse threat name from output
                threat = "Unknown threat"
                for line in result.stdout.split("\n"):
                    if "FOUND" in line:
                        threat = (
                            line.rsplit(":", 1)[-1].strip().replace("FOUND", "").strip()
                        )
                        break

                return ScanResult(
                    clean=False,
                    threat_found=threat,
                    scanner_used="clamdscan",
                    scan_time_ms=scan_time,
                )
            else:
                # Error
                return ScanResult(
                    clean=False,
                    error=f"clamdscan error: {result.stderr}",
                    scanner_used="clamdscan",
                )

        except FileNotFoundError:
            logger.warning("clamdscan command not found")
            return ScanResult(
                clean=False,
                error="clamdscan command not found",
                scanner_used="clamdscan",
            )
        except subprocess.TimeoutExpired:
            return ScanResult(
                clean=False,
                error=f"Scan timeout after {self.timeout}s",
                scanner_used="clamdscan",
            )
        except Exception as e:
            logger.error(f"CLI scan error: {e}", exc_info=True)
            return ScanResult(clean=False, error=str(e), scanner_used="clamdscan")

    async def health_check(self) -> Tuple[bool, str]:
        """
        Check scanner health

        Returns:
            Tuple of (healthy, message)
        """
        if not self.enabled:
            return True, "Virus scanning disabled"

        # Check daemon
        if self._check_clamd_connection():
            return True, f"ClamAV daemon available at {self.host}:{self.port}"

        # Check CLI
        if self.fallback_cli:
            try:
                subprocess.run(
                    ["clamdscan", "--version"], capture_output=True, timeout=5
                )
                return True, "ClamAV CLI available (daemon down)"
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                pass

        return False, "ClamAV scanner not available"


# Singleton instance
_scanner: Optional[VirusScannerService] = None


def get_virus_scanner() -> VirusScannerService:
    """Get singleton virus scanner instance"""
    global _scanner
    if _scanner is None:
        _scanner = VirusScannerService(
            enabled=os.getenv("CLAMAV_ENABLED"),
            host=os.getenv("CLAMAV_HOST", "localhost"),
            port=int(os.getenv("CLAMAV_PORT", "3310")),
            timeout=int(os.getenv("CLAMAV_TIMEOUT", "30")),
            fallback_cli=os.getenv("CLAMAV_FALLBACK_CLI", "true").lower()
            in ("true", "1", "yes"),
        )
    return _scanner
