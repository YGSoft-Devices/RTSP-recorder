"""Diagnostics widget - connectivity tests and support bundle generation."""
from __future__ import annotations

import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ..api_client import ApiClient

from ..storage import get_app_dir, load_profiles


class DiagnosticsWorker(QThread):
    """Background worker for running diagnostics."""

    log = Signal(str)
    finished = Signal(dict)

    def __init__(self, api_client, tests: list):
        super().__init__()
        self.api = api_client
        self.tests = tests

    def run(self):
        results = {}

        if "connection" in self.tests:
            self.log.emit("Testing connection...")
            results["connection"] = self._test_connection()

        if "endpoints" in self.tests:
            self.log.emit("Testing endpoints...")
            results["endpoints"] = self._test_endpoints()

        if "published" in self.tests:
            self.log.emit("Checking published root access...")
            results["published"] = self._test_published_access()

        self.finished.emit(results)

    def _test_connection(self) -> dict:
        """Test basic connectivity."""
        import socket
        import ssl
        from urllib.parse import urlparse

        result = {"dns": False, "tls": False, "auth": False, "details": []}
        
        try:
            url = self.api.cfg.base_url
            parsed = urlparse(url)
            host = parsed.hostname or "localhost"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)

            # DNS
            try:
                socket.gethostbyname(host)
                result["dns"] = True
                result["details"].append(f"✅ DNS: {host} resolved")
            except socket.gaierror as e:
                result["details"].append(f"❌ DNS: {host} failed - {e}")
                return result

            # TLS (if https)
            if parsed.scheme == "https":
                try:
                    ctx = ssl.create_default_context()
                    with socket.create_connection((host, port), timeout=10) as sock:
                        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                            cert = ssock.getpeercert()
                            result["tls"] = True
                            result["details"].append(f"✅ TLS: Certificate valid for {cert.get('subject', '?')}")
                except ssl.SSLError as e:
                    result["details"].append(f"❌ TLS: {e}")
                except Exception as e:
                    result["details"].append(f"⚠️ TLS check failed: {e}")
            else:
                result["tls"] = True
                result["details"].append("⚠️ TLS: Not using HTTPS")

            # Auth
            try:
                # Try to call an endpoint that requires auth
                self.api.list_channels()
                result["auth"] = True
                result["details"].append("✅ Auth: Token valid")
            except Exception as e:
                err_str = str(e)
                if "AUTH" in err_str.upper() or "401" in err_str:
                    result["details"].append(f"❌ Auth: {e}")
                else:
                    # Might be a different error, auth could still be OK
                    result["details"].append(f"⚠️ Auth check inconclusive: {e}")

        except Exception as e:
            result["details"].append(f"❌ Connection test failed: {e}")

        return result

    def _test_endpoints(self) -> list:
        """Test required API endpoints."""
        endpoints = [
            ("GET /api/admin/update-channels", lambda: self.api.list_channels()),
            ("GET /api/admin/device-updates", lambda: self.api.list_device_updates({"page": 1, "page_size": 1})),
            ("GET /api/admin/device-update-history", lambda: self.api.list_update_history({"page": 1, "page_size": 1})),
            ("GET /api/admin/updates/device-types", lambda: self.api.list_device_types()),
        ]

        results = []
        for name, func in endpoints:
            try:
                func()
                results.append({"endpoint": name, "status": "ok", "message": "✅ Available"})
            except Exception as e:
                # Check if it's a "not found" error vs auth error
                err_str = str(e).lower()
                if "404" in err_str or "not found" in err_str:
                    results.append({"endpoint": name, "status": "missing", "message": f"❌ Not found"})
                elif "auth" in err_str or "401" in err_str:
                    results.append({"endpoint": name, "status": "auth_error", "message": f"🔑 Auth required"})
                else:
                    results.append({"endpoint": name, "status": "error", "message": f"⚠️ {e}"})

        return results

    def _test_published_access(self) -> dict:
        """Test access to published root by listing device types."""
        result = {"accessible": False, "details": ""}
        try:
            resp = self.api.list_device_types()
            device_types = resp.get("device_types", {})
            count = len(device_types)
            result["accessible"] = True
            if count > 0:
                types_list = ", ".join(list(device_types.keys())[:5])
                result["details"] = f"✅ Published root accessible ({count} device types: {types_list})"
            else:
                result["details"] = "✅ Published root accessible (no device types yet)"
        except Exception as e:
            result["details"] = f"❌ {e}"
        return result


class DiagnosticsWidget(QWidget):
    """Diagnostics page with connectivity tests and support bundle."""

    def __init__(self, get_api_client):
        super().__init__()
        self.get_api_client = get_api_client
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Title
        title = QLabel("Diagnostics")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # Test buttons
        tests_group = QGroupBox("Connectivity Tests")
        tests_layout = QHBoxLayout()

        btn_connection = QPushButton("🔌 Test Connection")
        btn_connection.setMinimumHeight(40)
        btn_connection.clicked.connect(lambda: self._run_tests(["connection"]))

        btn_endpoints = QPushButton("🔗 Test Endpoints")
        btn_endpoints.setMinimumHeight(40)
        btn_endpoints.clicked.connect(lambda: self._run_tests(["endpoints"]))

        btn_published = QPushButton("📁 Check Published Root")
        btn_published.setMinimumHeight(40)
        btn_published.clicked.connect(lambda: self._run_tests(["published"]))

        btn_all = QPushButton("🧪 Run All Tests")
        btn_all.setMinimumHeight(40)
        btn_all.setStyleSheet("font-weight: bold;")
        btn_all.clicked.connect(lambda: self._run_tests(["connection", "endpoints", "published"]))

        tests_layout.addWidget(btn_connection)
        tests_layout.addWidget(btn_endpoints)
        tests_layout.addWidget(btn_published)
        tests_layout.addWidget(btn_all)
        tests_group.setLayout(tests_layout)
        layout.addWidget(tests_group)

        # Output
        output_group = QGroupBox("Test Results")
        output_layout = QVBoxLayout()
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(300)
        output_layout.addWidget(self.output)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # Support bundle
        bundle_group = QGroupBox("Support Bundle")
        bundle_layout = QHBoxLayout()

        bundle_layout.addWidget(QLabel("Generate a support bundle with logs, config snapshot, and last API errors:"))

        btn_bundle = QPushButton("📦 Generate Support Bundle")
        btn_bundle.setMinimumHeight(36)
        btn_bundle.clicked.connect(self._generate_support_bundle)
        bundle_layout.addWidget(btn_bundle)

        bundle_layout.addStretch()
        bundle_group.setLayout(bundle_layout)
        layout.addWidget(bundle_group)

        # Environment info
        env_group = QGroupBox("Environment")
        env_layout = QVBoxLayout()
        self.env_info = QTextEdit()
        self.env_info.setReadOnly(True)
        self.env_info.setMaximumHeight(120)
        self._populate_env_info()
        env_layout.addWidget(self.env_info)
        env_group.setLayout(env_layout)
        layout.addWidget(env_group)

        layout.addStretch()

    def _populate_env_info(self):
        """Display environment information."""
        info = []
        info.append(f"OS: {platform.system()} {platform.release()}")
        info.append(f"Python: {platform.python_version()}")
        info.append(f"Machine: {platform.machine()}")
        info.append(f"App Dir: {get_app_dir()}")

        # Check if token is set
        profiles = load_profiles()
        active = profiles.get("active")
        info.append(f"Active Profile: {active or 'None'}")

        self.env_info.setPlainText("\n".join(info))

    def _run_tests(self, tests: list):
        """Run diagnostic tests in background."""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Busy", "Tests already running")
            return

        self.output.clear()
        self.output.append(f"Starting tests: {', '.join(tests)}\n")

        try:
            api = self.get_api_client()
            self.worker = DiagnosticsWorker(api, tests)
            self.worker.log.connect(self._on_log)
            self.worker.finished.connect(self._on_tests_finished)
            self.worker.start()
        except Exception as e:
            self.output.append(f"❌ Failed to start tests: {e}")

    def _on_log(self, message: str):
        self.output.append(message)

    def _on_tests_finished(self, results: dict):
        self.output.append("\n=== Results ===\n")

        if "connection" in results:
            conn = results["connection"]
            self.output.append("Connection Test:")
            for detail in conn.get("details", []):
                self.output.append(f"  {detail}")
            self.output.append("")

        if "endpoints" in results:
            self.output.append("Endpoint Tests:")
            for ep in results["endpoints"]:
                self.output.append(f"  {ep['endpoint']}: {ep['message']}")
            self.output.append("")

        if "published" in results:
            pub = results["published"]
            self.output.append(f"Published Root: {pub.get('details', '?')}")

        self.output.append("\n✅ Tests complete")

    def _generate_support_bundle(self):
        """Generate a support bundle ZIP file."""
        try:
            import zipfile

            # Choose save location
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Support Bundle",
                f"support_bundle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                "ZIP Files (*.zip)",
            )
            if not file_path:
                return

            app_dir = get_app_dir()

            with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Add log files
                logs_dir = app_dir / "logs"
                if logs_dir.exists():
                    for log_file in logs_dir.glob("*.log*"):
                        zf.write(log_file, f"logs/{log_file.name}")

                # Add config (redacted)
                profiles = load_profiles()
                # Redact sensitive info
                redacted_profiles = {
                    "profiles": [
                        {k: v for k, v in p.items() if k != "token"}
                        for p in profiles.get("profiles", [])
                    ],
                    "active": profiles.get("active"),
                }
                zf.writestr("config/profiles_redacted.json", json.dumps(redacted_profiles, indent=2))

                # Add environment info
                env_info = {
                    "os": f"{platform.system()} {platform.release()}",
                    "python": platform.python_version(),
                    "machine": platform.machine(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "app_dir": str(app_dir),
                }
                zf.writestr("environment.json", json.dumps(env_info, indent=2))

                # Add current test output
                current_output = self.output.toPlainText()
                if current_output:
                    zf.writestr("diagnostics_output.txt", current_output)

            self.output.append(f"\n✅ Support bundle saved to: {file_path}")
            QMessageBox.information(self, "Success", f"Support bundle saved to:\n{file_path}")

        except Exception as e:
            self.output.append(f"\n❌ Failed to generate support bundle: {e}")
            QMessageBox.warning(self, "Error", str(e))
