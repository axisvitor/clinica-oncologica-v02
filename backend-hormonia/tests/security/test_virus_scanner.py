"""
Comprehensive Virus Scanner Tests using ClamAV

Tests P2 Implementation: Virus scanning for file uploads
Tests both daemon and CLI modes, error handling, and EICAR test file detection.
Priority: P2 - High (Security Feature)
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import tempfile
import subprocess

from app.services.virus_scanner import (
    VirusScannerService,
    ScanResult,
    get_virus_scanner
)


# EICAR test virus signature (standard test file for antivirus)
EICAR_SIGNATURE = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'


class TestVirusScannerService:
    """Test virus scanner service functionality"""

    def test_scanner_disabled(self):
        """Test scanner behavior when disabled"""
        scanner = VirusScannerService(enabled=False)

        assert scanner.enabled is False
        assert scanner._clamd_available is False

    def test_scanner_enabled_production(self, mocker):
        """Test scanner automatically enables in production"""
        mocker.patch.dict('os.environ', {'ENVIRONMENT': 'production'})

        with patch.object(VirusScannerService, '_check_clamd_connection', return_value=False):
            scanner = VirusScannerService()
            # Note: Will be enabled but daemon check may fail
            assert scanner._should_enable() is True

    def test_scanner_disabled_development(self, mocker):
        """Test scanner defaults to disabled in development"""
        mocker.patch.dict('os.environ', {'ENVIRONMENT': 'development', 'CLAMAV_ENABLED': ''}, clear=True)

        scanner = VirusScannerService(enabled=None)
        assert scanner._should_enable() is False

    @pytest.mark.asyncio
    async def test_scan_file_when_disabled(self, tmp_path):
        """Test scanning returns clean when scanner is disabled"""
        scanner = VirusScannerService(enabled=False)

        test_file = tmp_path / "test.txt"
        test_file.write_text("Clean file content")

        result = await scanner.scan_file(str(test_file))

        assert result.clean is True
        assert result.scanner_used == "disabled"
        assert result.threat_found is None
        assert result.error is None

    @pytest.mark.asyncio
    async def test_scan_file_not_found(self):
        """Test scanning non-existent file"""
        scanner = VirusScannerService(enabled=True)
        scanner._clamd_available = False
        scanner.fallback_cli = False

        result = await scanner.scan_file("/nonexistent/file.txt")

        assert result.clean is False
        assert "File not found" in result.error
        assert result.scanner_used == "none"

    @pytest.mark.asyncio
    async def test_scan_clean_file_with_daemon(self, tmp_path, mocker):
        """Test scanning clean file using ClamAV daemon"""
        test_file = tmp_path / "clean.txt"
        test_file.write_text("This is a clean file")

        # Mock pyclamd module
        mock_pyclamd = MagicMock()
        mock_clamd = MagicMock()
        mock_clamd.ping.return_value = True
        mock_clamd.scan_file.return_value = None  # None = clean
        mock_pyclamd.ClamdNetworkSocket.return_value = mock_clamd

        mocker.patch.dict('sys.modules', {'pyclamd': mock_pyclamd})

        scanner = VirusScannerService(enabled=True, host="localhost", port=3310)
        scanner._clamd_available = True

        result = await scanner.scan_file(str(test_file))

        assert result.clean is True
        assert result.scanner_used == "clamd"
        assert result.threat_found is None
        assert result.error is None
        assert result.scan_time_ms >= 0

    @pytest.mark.asyncio
    async def test_scan_infected_file_with_daemon(self, tmp_path, mocker):
        """Test detecting EICAR test file using ClamAV daemon"""
        test_file = tmp_path / "eicar.txt"
        test_file.write_bytes(EICAR_SIGNATURE)

        # Mock pyclamd to detect virus
        mock_pyclamd = MagicMock()
        mock_clamd = MagicMock()
        mock_clamd.ping.return_value = True
        mock_clamd.scan_file.return_value = {
            str(test_file): ('FOUND', 'Eicar-Test-Signature')
        }
        mock_pyclamd.ClamdNetworkSocket.return_value = mock_clamd

        mocker.patch.dict('sys.modules', {'pyclamd': mock_pyclamd})

        scanner = VirusScannerService(enabled=True)
        scanner._clamd_available = True

        result = await scanner.scan_file(str(test_file))

        assert result.clean is False
        assert result.scanner_used == "clamd"
        assert result.threat_found == 'Eicar-Test-Signature'
        assert result.error is None

    @pytest.mark.asyncio
    async def test_daemon_not_responding(self, tmp_path, mocker):
        """Test fallback when daemon doesn't respond to ping"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Clean file")

        # Mock pyclamd with non-responsive daemon
        mock_pyclamd = MagicMock()
        mock_clamd = MagicMock()
        mock_clamd.ping.return_value = False  # Daemon not responding
        mock_pyclamd.ClamdNetworkSocket.return_value = mock_clamd

        mocker.patch.dict('sys.modules', {'pyclamd': mock_pyclamd})

        # Mock successful CLI scan
        mock_result = Mock()
        mock_result.returncode = 0  # Clean
        mock_result.stdout = ""
        mock_result.stderr = ""
        mocker.patch('subprocess.run', return_value=mock_result)

        scanner = VirusScannerService(enabled=True, fallback_cli=True)
        scanner._clamd_available = True

        result = await scanner.scan_file(str(test_file))

        # Should fall back to CLI
        assert result.scanner_used == "clamdscan"

    @pytest.mark.asyncio
    async def test_scan_clean_file_with_cli(self, tmp_path, mocker):
        """Test scanning clean file using clamdscan CLI"""
        test_file = tmp_path / "clean.txt"
        test_file.write_text("Clean content")

        # Mock subprocess.run for clamdscan
        mock_result = Mock()
        mock_result.returncode = 0  # Clean file
        mock_result.stdout = f"{test_file}: OK\n"
        mock_result.stderr = ""
        mocker.patch('subprocess.run', return_value=mock_result)

        scanner = VirusScannerService(enabled=True, fallback_cli=True)
        scanner._clamd_available = False

        result = await scanner.scan_file(str(test_file))

        assert result.clean is True
        assert result.scanner_used == "clamdscan"
        assert result.threat_found is None
        assert result.scan_time_ms >= 0

    @pytest.mark.asyncio
    async def test_scan_infected_file_with_cli(self, tmp_path, mocker):
        """Test detecting virus with clamdscan CLI"""
        test_file = tmp_path / "infected.txt"
        test_file.write_bytes(EICAR_SIGNATURE)

        # Mock subprocess.run for infected file
        mock_result = Mock()
        mock_result.returncode = 1  # Virus found
        mock_result.stdout = f"{test_file}: Eicar-Test-Signature FOUND\n"
        mock_result.stderr = ""
        mocker.patch('subprocess.run', return_value=mock_result)

        scanner = VirusScannerService(enabled=True, fallback_cli=True)
        scanner._clamd_available = False

        result = await scanner.scan_file(str(test_file))

        assert result.clean is False
        assert result.scanner_used == "clamdscan"
        assert "Eicar-Test-Signature" in result.threat_found
        assert result.error is None

    @pytest.mark.asyncio
    async def test_cli_command_not_found(self, tmp_path, mocker):
        """Test handling when clamdscan command is not installed"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test")

        # Mock FileNotFoundError
        mocker.patch('subprocess.run', side_effect=FileNotFoundError("clamdscan not found"))

        scanner = VirusScannerService(enabled=True, fallback_cli=True)
        scanner._clamd_available = False

        result = await scanner.scan_file(str(test_file))

        assert result.clean is False
        assert result.scanner_used == "clamdscan"
        assert "command not found" in result.error

    @pytest.mark.asyncio
    async def test_scan_timeout_cli(self, tmp_path, mocker):
        """Test timeout handling for CLI scanner"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test")

        # Mock timeout
        mocker.patch('subprocess.run', side_effect=subprocess.TimeoutExpired(
            cmd=['clamdscan'], timeout=5
        ))

        scanner = VirusScannerService(enabled=True, timeout=5, fallback_cli=True)
        scanner._clamd_available = False

        result = await scanner.scan_file(str(test_file))

        assert result.clean is False
        assert result.scanner_used == "clamdscan"
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_cli_scanner_error(self, tmp_path, mocker):
        """Test CLI scanner returning error code"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test")

        # Mock error code 2+ (error, not virus)
        mock_result = Mock()
        mock_result.returncode = 2
        mock_result.stdout = ""
        mock_result.stderr = "ERROR: Cannot access file"
        mocker.patch('subprocess.run', return_value=mock_result)

        scanner = VirusScannerService(enabled=True, fallback_cli=True)
        scanner._clamd_available = False

        result = await scanner.scan_file(str(test_file))

        assert result.clean is False
        assert result.scanner_used == "clamdscan"
        assert "error" in result.error.lower()

    @pytest.mark.asyncio
    async def test_no_scanner_available_fail_open(self, tmp_path):
        """Test fail-open behavior when no scanner is available"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test")

        scanner = VirusScannerService(enabled=True, fallback_cli=False)
        scanner._clamd_available = False

        result = await scanner.scan_file(str(test_file))

        # Should fail open (return clean) for availability
        assert result.clean is True
        assert result.scanner_used == "none"
        assert "No scanner available" in result.error

    @pytest.mark.asyncio
    async def test_daemon_exception_handling(self, tmp_path, mocker):
        """Test exception handling in daemon scan"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test")

        # Mock pyclamd with exception
        mock_pyclamd = MagicMock()
        mock_clamd = MagicMock()
        mock_clamd.ping.return_value = True
        mock_clamd.scan_file.side_effect = Exception("Connection error")
        mock_pyclamd.ClamdNetworkSocket.return_value = mock_clamd

        mocker.patch.dict('sys.modules', {'pyclamd': mock_pyclamd})

        # Mock CLI fallback
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mocker.patch('subprocess.run', return_value=mock_result)

        scanner = VirusScannerService(enabled=True, fallback_cli=True)
        scanner._clamd_available = True

        result = await scanner.scan_file(str(test_file))

        # Should fall back to CLI after daemon error
        assert result.scanner_used == "clamdscan"

    @pytest.mark.asyncio
    async def test_pyclamd_not_installed(self, tmp_path, mocker):
        """Test fallback when pyclamd is not installed"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test")

        # Remove pyclamd from sys.modules
        mocker.patch.dict('sys.modules', {'pyclamd': None})

        # Mock successful CLI
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mocker.patch('subprocess.run', return_value=mock_result)

        scanner = VirusScannerService(enabled=True, fallback_cli=True)
        scanner._clamd_available = True

        result = await scanner.scan_file(str(test_file))

        # Should use CLI
        assert result.scanner_used == "clamdscan"


class TestVirusScannerHealth:
    """Test health check functionality"""

    @pytest.mark.asyncio
    async def test_health_check_disabled(self):
        """Test health check when scanner is disabled"""
        scanner = VirusScannerService(enabled=False)

        healthy, message = await scanner.health_check()

        assert healthy is True
        assert "disabled" in message.lower()

    @pytest.mark.asyncio
    async def test_health_check_daemon_available(self, mocker):
        """Test health check with available daemon"""
        mocker.patch.object(VirusScannerService, '_check_clamd_connection', return_value=True)

        scanner = VirusScannerService(enabled=True, host="localhost", port=3310)

        healthy, message = await scanner.health_check()

        assert healthy is True
        assert "daemon available" in message.lower()

    @pytest.mark.asyncio
    async def test_health_check_cli_fallback(self, mocker):
        """Test health check falling back to CLI"""
        mocker.patch.object(VirusScannerService, '_check_clamd_connection', return_value=False)

        # Mock CLI available
        mock_result = Mock()
        mock_result.returncode = 0
        mocker.patch('subprocess.run', return_value=mock_result)

        scanner = VirusScannerService(enabled=True, fallback_cli=True)

        healthy, message = await scanner.health_check()

        assert healthy is True
        assert "cli available" in message.lower()

    @pytest.mark.asyncio
    async def test_health_check_no_scanner(self, mocker):
        """Test health check when no scanner is available"""
        mocker.patch.object(VirusScannerService, '_check_clamd_connection', return_value=False)

        # Mock CLI unavailable
        mocker.patch('subprocess.run', side_effect=FileNotFoundError())

        scanner = VirusScannerService(enabled=True, fallback_cli=True)

        healthy, message = await scanner.health_check()

        assert healthy is False
        assert "not available" in message.lower()


class TestVirusScannerSingleton:
    """Test singleton pattern"""

    def test_get_virus_scanner_singleton(self, mocker):
        """Test get_virus_scanner returns same instance"""
        mocker.patch.dict('os.environ', {
            'CLAMAV_ENABLED': 'false',
            'CLAMAV_HOST': 'testhost',
            'CLAMAV_PORT': '3333'
        })

        # Reset singleton
        import app.services.virus_scanner as vs
        vs._scanner = None

        scanner1 = get_virus_scanner()
        scanner2 = get_virus_scanner()

        assert scanner1 is scanner2
        assert scanner1.host == 'testhost'
        assert scanner1.port == 3333


class TestVirusScannerIntegration:
    """Integration tests with file operations"""

    @pytest.mark.asyncio
    async def test_scan_multiple_files_sequentially(self, tmp_path):
        """Test scanning multiple files in sequence"""
        scanner = VirusScannerService(enabled=False)

        files = []
        for i in range(5):
            f = tmp_path / f"file{i}.txt"
            f.write_text(f"Content {i}")
            files.append(f)

        results = []
        for f in files:
            result = await scanner.scan_file(str(f))
            results.append(result)

        assert len(results) == 5
        assert all(r.clean for r in results)

    @pytest.mark.asyncio
    async def test_scan_large_file_with_timeout(self, tmp_path, mocker):
        """Test timeout with large file"""
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b'0' * (10 * 1024 * 1024))  # 10MB

        # Mock timeout
        mocker.patch('subprocess.run', side_effect=subprocess.TimeoutExpired(
            cmd=['clamdscan'], timeout=1
        ))

        scanner = VirusScannerService(enabled=True, timeout=1, fallback_cli=True)
        scanner._clamd_available = False

        result = await scanner.scan_file(str(large_file))

        assert result.clean is False
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_scan_with_special_characters_in_path(self, tmp_path, mocker):
        """Test scanning file with special characters in path"""
        special_file = tmp_path / "test file (with spaces) & special.txt"
        special_file.write_text("Test")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mocker.patch('subprocess.run', return_value=mock_result)

        scanner = VirusScannerService(enabled=True, fallback_cli=True)
        scanner._clamd_available = False

        result = await scanner.scan_file(str(special_file))

        assert result.clean is True


class TestVirusScannerConfiguration:
    """Test configuration options"""

    def test_custom_configuration(self):
        """Test custom scanner configuration"""
        scanner = VirusScannerService(
            enabled=True,
            host="custom.host",
            port=9999,
            timeout=60,
            fallback_cli=False
        )

        assert scanner.enabled is True
        assert scanner.host == "custom.host"
        assert scanner.port == 9999
        assert scanner.timeout == 60
        assert scanner.fallback_cli is False

    def test_default_configuration(self, mocker):
        """Test default configuration values"""
        mocker.patch.dict('os.environ', {'ENVIRONMENT': 'development'}, clear=True)

        with patch.object(VirusScannerService, '_check_clamd_connection', return_value=False):
            scanner = VirusScannerService()

            assert scanner.host == "localhost"
            assert scanner.port == 3310
            assert scanner.timeout == 30
            assert scanner.fallback_cli is True
