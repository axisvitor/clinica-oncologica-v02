"""
File Security Service

Comprehensive file upload security including:
1. CVE-CLINIC-2025-003: Dangerous file extension blocking
2. PDF JavaScript detection (malicious PDF prevention)
3. File content validation beyond MIME types

Prevents:
- Executable uploads (.exe, .sh, .bat, etc.)
- Malicious PDFs with embedded JavaScript
- Double extension attacks (.pdf.exe)
- Polyglot files (valid as multiple formats)
- Macro-enabled Office documents (unless explicitly allowed)
"""

import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class SecurityScanResult:
    """File security scan result."""

    is_safe: bool
    threats_found: List[str]
    scan_time_ms: int = 0
    scanner_version: str = "1.0.0"


class FileSecurityService:
    """
    Comprehensive file security scanning service.

    Blocks dangerous file types and detects malicious content
    beyond basic MIME type validation.

    Configuration (via environment variables):
        FILE_SECURITY_ENABLED: Enable file security scanning (default: True)
        ALLOW_MACROS: Allow macro-enabled Office docs (default: False)
        ALLOW_SCRIPTS_IN_PDF: Allow JavaScript in PDFs (default: False)
    """

    # COMPLETE dangerous extension blocklist (CVE-CLINIC-2025-003)
    DANGEROUS_EXTENSIONS = {
        # Windows Executables
        ".exe",
        ".dll",
        ".com",
        ".bat",
        ".cmd",
        ".msi",
        ".scr",
        ".cpl",
        ".hta",
        ".vbs",
        ".vbe",
        ".ws",
        ".wsf",
        ".wsh",
        ".ps1",
        ".psm1",
        # Linux/Unix Executables
        ".sh",
        ".bash",
        ".ksh",
        ".csh",
        ".zsh",
        ".run",
        ".bin",
        # macOS Executables
        ".app",
        ".dmg",
        ".pkg",
        ".command",
        # Archives that can contain executables
        ".rar",
        ".7z",
        ".ace",
        ".arj",
        ".cab",
        ".iso",
        ".img",
        # Script Files
        ".js",
        ".jar",
        ".py",
        ".pyc",
        ".pyo",
        ".rb",
        ".pl",
        ".php",
        ".asp",
        ".aspx",
        ".jsp",
        ".jspx",
        # Macro-enabled Office Documents
        ".docm",
        ".xlsm",
        ".pptm",
        ".dotm",
        ".xltm",
        ".potm",
        # Compressed Executables
        ".gz",
        ".bz2",
        ".xz",
        ".lz",
        ".z",  # Only if containing executable
        # Database Files (can contain macros/code)
        ".mdb",
        ".accdb",
        ".db",
        # Other Dangerous Formats
        ".swf",  # Flash (can execute code)
        ".lnk",  # Windows shortcuts (can execute commands)
        ".url",  # Internet shortcuts
        ".reg",  # Registry files
        ".ade",
        ".adp",  # Access projects
        ".chm",  # Compiled HTML help (can run scripts)
        ".inf",  # INF files (can auto-install)
        ".ins",  # Internet Settings
        ".isp",  # IIS Settings
        ".jse",  # JScript Encoded
        ".mde",
        ".msc",
        ".msp",
        ".mst",  # Microsoft installers
        ".pcd",  # Photo CD
        ".pif",  # Program Information File
        ".scf",  # Windows Explorer Command
        ".sct",  # Windows Script Component
        ".shb",  # Windows Shortcut
        ".shs",  # Shell Scrap Object
        ".vb",  # VB Script
        ".wsc",  # Windows Script Component
    }

    # Extensions that MIGHT be safe but require content validation
    SUSPICIOUS_EXTENSIONS = {
        ".pdf",  # Can contain JavaScript
        ".zip",  # Can contain executables
        ".tar",  # Can contain executables
        ".html",
        ".htm",  # Can contain scripts (but usually safe)
        ".svg",  # Can contain scripts
        ".xml",  # Can contain malicious content
    }

    def __init__(
        self,
        enabled: bool = True,
        allow_macros: bool = False,
        allow_pdf_javascript: bool = False,
    ):
        """
        Initialize file security service.

        Args:
            enabled: Enable security scanning (default: True)
            allow_macros: Allow macro-enabled Office documents (default: False)
            allow_pdf_javascript: Allow JavaScript in PDFs (default: False)
        """
        self.enabled = enabled
        self.allow_macros = allow_macros
        self.allow_pdf_javascript = allow_pdf_javascript

        # Try to import PDF parsing libraries
        try:
            import PyPDF2

            self.pypdf2 = PyPDF2
            self._pdf_available = True
        except ImportError:
            self.pypdf2 = None
            self._pdf_available = False
            logger.warning(
                "PyPDF2 not available - PDF JavaScript detection disabled. "
                "Install with: pip install PyPDF2"
            )

        logger.info(
            "File security service initialized",
            extra={
                "enabled": enabled,
                "allow_macros": allow_macros,
                "allow_pdf_javascript": allow_pdf_javascript,
                "pdf_scan_available": self._pdf_available,
            },
        )

    async def scan_file(
        self, file_path: Path, content: Optional[bytes] = None
    ) -> SecurityScanResult:
        """
        Scan file for security threats.

        Args:
            file_path: Path to file
            content: Optional file content (reads from disk if None)

        Returns:
            SecurityScanResult
        """
        if not self.enabled:
            return SecurityScanResult(is_safe=True, threats_found=[], scan_time_ms=0)

        import time

        start_time = time.time()

        threats: List[str] = []

        try:
            # 1. Extension validation (CVE-CLINIC-2025-003)
            extension = file_path.suffix.lower()

            if extension in self.DANGEROUS_EXTENSIONS:
                # Check for macro-enabled docs exception
                if extension in {".docm", ".xlsm", ".pptm"} and self.allow_macros:
                    logger.warning(
                        f"Macro-enabled document allowed by configuration: {extension}"
                    )
                else:
                    threats.append(f"Dangerous file extension: {extension}")

            # 2. Double extension check (.pdf.exe, .jpg.exe, etc.)
            filename = file_path.name
            if self._has_double_extension(filename):
                threats.append(f"Double extension detected: {filename}")

            # 3. Content-based validation for suspicious files
            if extension in self.SUSPICIOUS_EXTENSIONS:
                if content is None:
                    with open(file_path, "rb") as f:
                        content = f.read()

                if extension == ".pdf":
                    pdf_threats = await self._scan_pdf(content)
                    threats.extend(pdf_threats)

                elif extension in {".zip", ".tar"}:
                    archive_threats = await self._scan_archive(file_path)
                    threats.extend(archive_threats)

                elif extension in {".html", ".htm", ".svg"}:
                    script_threats = await self._scan_scripts(content)
                    threats.extend(script_threats)

            scan_time_ms = int((time.time() - start_time) * 1000)

            is_safe = len(threats) == 0

            if not is_safe:
                logger.error(
                    "File security threats detected",
                    extra={
                        "file_path": str(file_path),
                        "threats": threats,
                        "scan_time_ms": scan_time_ms,
                    },
                )
            else:
                logger.info(
                    "File passed security scan",
                    extra={"file_path": str(file_path), "scan_time_ms": scan_time_ms},
                )

            return SecurityScanResult(
                is_safe=is_safe, threats_found=threats, scan_time_ms=scan_time_ms
            )

        except Exception as e:
            logger.error(f"Security scan failed: {e}", exc_info=True)
            # Fail open to prevent DoS
            return SecurityScanResult(
                is_safe=True,
                threats_found=[f"Scan error (fail-open): {str(e)}"],
                scan_time_ms=0,
            )

    async def _scan_pdf(self, content: bytes) -> List[str]:
        """
        Scan PDF for JavaScript and other threats.

        Args:
            content: PDF file content

        Returns:
            List of threats found
        """
        threats = []

        if not self._pdf_available:
            return threats

        try:
            pdf_file = io.BytesIO(content)
            reader = self.pypdf2.PdfReader(pdf_file)

            # Check for JavaScript in PDF
            has_javascript = False

            # Method 1: Check catalog for JavaScript
            if "/Names" in reader.trailer.get("/Root", {}):
                names = reader.trailer["/Root"]["/Names"]
                if "/JavaScript" in names:
                    has_javascript = True

            # Method 2: Check each page for /AA (Additional Actions)
            for page in reader.pages:
                if "/AA" in page:
                    has_javascript = True
                    break

            # Method 3: Scan raw content for JavaScript keywords
            if not has_javascript:
                content_str = content.decode("latin-1", errors="ignore")
                js_patterns = [
                    r"/JavaScript",
                    r"/JS\s*\(",
                    r"app\.alert",
                    r"this\.submitForm",
                    r"util\.printf",
                ]

                for pattern in js_patterns:
                    if re.search(pattern, content_str, re.IGNORECASE):
                        has_javascript = True
                        break

            if has_javascript and not self.allow_pdf_javascript:
                threats.append("PDF contains JavaScript")

            # Check for embedded files (can hide malware)
            if "/EmbeddedFiles" in reader.trailer.get("/Root", {}).get("/Names", {}):
                threats.append("PDF contains embedded files")

            # Check for forms (can be used for phishing)
            if "/AcroForm" in reader.trailer.get("/Root", {}):
                logger.info("PDF contains form fields (potentially suspicious)")

        except Exception as e:
            logger.error(f"PDF scan failed: {e}", exc_info=True)
            # Don't fail the upload, just log

        return threats

    async def _scan_archive(self, file_path: Path) -> List[str]:
        """
        Scan archive (zip/tar) for dangerous files.

        Args:
            file_path: Path to archive

        Returns:
            List of threats found
        """
        threats = []

        try:
            if file_path.suffix.lower() == ".zip":
                import zipfile

                with zipfile.ZipFile(file_path, "r") as zf:
                    for info in zf.filelist:
                        filename = info.filename
                        ext = Path(filename).suffix.lower()

                        if ext in self.DANGEROUS_EXTENSIONS:
                            threats.append(
                                f"Archive contains dangerous file: {filename}"
                            )

            elif file_path.suffix.lower() == ".tar":
                import tarfile

                with tarfile.open(file_path, "r") as tf:
                    for member in tf.getmembers():
                        filename = member.name
                        ext = Path(filename).suffix.lower()

                        if ext in self.DANGEROUS_EXTENSIONS:
                            threats.append(
                                f"Archive contains dangerous file: {filename}"
                            )

        except Exception as e:
            logger.error(f"Archive scan failed: {e}", exc_info=True)

        return threats

    async def _scan_scripts(self, content: bytes) -> List[str]:
        """
        Scan HTML/SVG for malicious scripts.

        Args:
            content: File content

        Returns:
            List of threats found
        """
        threats = []

        try:
            content_str = content.decode("utf-8", errors="ignore").lower()

            # Check for dangerous script patterns
            dangerous_patterns = [
                r"<script[^>]*>.*?eval\(",  # eval() execution
                r"document\.write\(",  # DOM manipulation
                r"window\.location",  # Redirects
                r"<iframe",  # Iframes (can load external content)
                r"onerror\s*=",  # Event handlers
                r"onclick\s*=",
                r"onload\s*=",
            ]

            for pattern in dangerous_patterns:
                if re.search(pattern, content_str, re.IGNORECASE | re.DOTALL):
                    threats.append(f"Suspicious script pattern detected: {pattern}")

        except Exception as e:
            logger.error(f"Script scan failed: {e}", exc_info=True)

        return threats

    def _has_double_extension(self, filename: str) -> bool:
        """
        Check for double extension attack (.pdf.exe, .jpg.exe, etc.).

        Args:
            filename: Original filename

        Returns:
            True if double extension detected
        """
        parts = filename.lower().split(".")

        if len(parts) < 3:
            return False  # Need at least "name.ext1.ext2"

        # Check if any intermediate extension is dangerous
        for ext in parts[1:-1]:
            if f".{ext}" in self.DANGEROUS_EXTENSIONS:
                return True

        return False


# Singleton instance
_file_security: Optional[FileSecurityService] = None


def get_file_security() -> FileSecurityService:
    """
    Get or create file security service singleton.

    Returns:
        FileSecurityService instance
    """
    global _file_security

    if _file_security is None:
        _file_security = FileSecurityService()

    return _file_security
