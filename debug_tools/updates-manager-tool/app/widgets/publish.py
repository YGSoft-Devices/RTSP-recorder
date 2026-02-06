"""Publish Release widget - core workflow for publishing updates."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ..api_client import ApiClient

from ..publisher import build_archive, build_manifest, compute_sha256, validate_manifest, write_manifest
from ..storage import load_publish_history, save_publish_history


class PublishWorker(QThread):
    """Background worker for archive building and upload."""

    progress = Signal(int, str)  # percent, message
    finished = Signal(bool, str, dict)  # success, message, result_data

    def __init__(self, api_client, params: dict):
        super().__init__()
        self.api = api_client
        self.params = params

    def run(self):
        try:
            source_path = Path(self.params["source_path"])
            device_type = self.params["device_type"]
            distribution = self.params["distribution"]
            version = self.params["version"]
            notes = self.params.get("notes", "")
            archive_format = self.params.get("archive_format", "tar.gz")
            dry_run = self.params.get("dry_run", False)

            # Step 1: Build archive (if folder)
            self.progress.emit(10, "Checking source...")
            if source_path.is_dir():
                self.progress.emit(20, "Building archive from folder...")
                archive_name = f"update.{archive_format}"
                temp_dir = Path(os.environ.get("TEMP", "/tmp"))
                archive_path = temp_dir / f"{device_type}_{distribution}_{version}_{archive_name}"
                build_archive(source_path, archive_path, fmt=archive_format)
            else:
                archive_path = source_path
                archive_name = source_path.name

            # Step 2: Compute sha256
            self.progress.emit(40, "Computing SHA256...")
            sha256, size = compute_sha256(archive_path)

            # Step 3: Build manifest
            self.progress.emit(50, "Building manifest...")
            manifest = build_manifest(
                device_type=device_type,
                distribution=distribution,
                version=version,
                archive_name=archive_name,
                sha256=sha256,
                size=size,
                notes=notes,
            )

            if not validate_manifest(manifest):
                self.finished.emit(False, "Manifest validation failed", {})
                return

            # Step 4: Write manifest to temp file
            manifest_path = archive_path.parent / "manifest.json"
            write_manifest(manifest_path, manifest)

            if dry_run:
                self.progress.emit(100, "Dry run complete")
                self.finished.emit(True, "Dry run successful - no upload performed", {
                    "manifest": manifest,
                    "archive_path": str(archive_path),
                    "manifest_path": str(manifest_path),
                })
                return

            # Step 5: Upload
            self.progress.emit(60, "Uploading to server...")
            with open(manifest_path, "rb") as mf, open(archive_path, "rb") as af:
                files = {
                    "manifest": ("manifest.json", mf, "application/json"),
                    "archive": (archive_name, af, "application/octet-stream"),
                }
                data = {
                    "device_type": device_type,
                    "distribution": distribution,
                    "version": version,
                }
                # Check for signature file
                sig_path = archive_path.parent / "manifest.sig"
                if sig_path.exists():
                    with open(sig_path, "rb") as sf:
                        files["signature"] = ("manifest.sig", sf, "application/octet-stream")
                        result = self.api.publish_update(files, data=data)
                else:
                    result = self.api.publish_update(files, data=data)

            self.progress.emit(90, "Verifying upload...")

            # Step 6: Verify
            verify_result = self.api.verify_artifacts(device_type, distribution, version)

            self.progress.emit(100, "Complete!")
            self.finished.emit(True, "Publish successful", {
                "manifest": manifest,
                "publish_result": result,
                "verify_result": verify_result,
            })

        except Exception as e:
            self.finished.emit(False, str(e), {})


class PublishWidget(QWidget):
    """Publish Release page with full workflow."""

    def __init__(self, get_api_client):
        super().__init__()
        self.get_api_client = get_api_client
        self.worker: Optional[PublishWorker] = None
        self._device_types_cache = {}  # device_type -> [distributions]
        self._build_ui()
        self._load_device_types()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Title
        title = QLabel("Publish Release")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # Main content in horizontal layout
        content_layout = QHBoxLayout()

        # Left: Input form
        form_group = QGroupBox("Release Information")
        form_layout = QFormLayout()

        # Device Type: Editable ComboBox with refresh button
        device_type_layout = QHBoxLayout()
        self.device_type = QComboBox()
        self.device_type.setEditable(True)
        self.device_type.setMinimumWidth(200)
        self.device_type.lineEdit().setPlaceholderText("Select or enter device type...")
        self.device_type.currentTextChanged.connect(self._on_device_type_changed)
        
        btn_refresh_types = QPushButton("🔄")
        btn_refresh_types.setFixedWidth(36)
        btn_refresh_types.setToolTip("Refresh device types from server")
        btn_refresh_types.clicked.connect(self._load_device_types)
        
        device_type_layout.addWidget(self.device_type)
        device_type_layout.addWidget(btn_refresh_types)
        form_layout.addRow("Device Type:", device_type_layout)

        # Distribution: Editable ComboBox (populated based on device type)
        self.distribution = QComboBox()
        self.distribution.setEditable(True)
        self.distribution.setMinimumWidth(200)
        self.distribution.lineEdit().setPlaceholderText("Select or enter distribution...")
        form_layout.addRow("Distribution:", self.distribution)

        self.version = QLineEdit()
        self.version.setPlaceholderText("e.g., 1.2.3")
        form_layout.addRow("Version:", self.version)

        self.channel = QLineEdit()
        self.channel.setPlaceholderText("e.g., default (optional)")
        form_layout.addRow("Channel:", self.channel)

        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Release notes (optional)")
        self.notes.setMaximumHeight(80)
        form_layout.addRow("Notes:", self.notes)

        # Source selection
        source_layout = QHBoxLayout()
        self.source_path = QLineEdit()
        self.source_path.setPlaceholderText("Select folder or archive file")
        btn_browse_folder = QPushButton("📁 Folder")
        btn_browse_file = QPushButton("📄 File")
        btn_browse_folder.clicked.connect(self._browse_folder)
        btn_browse_file.clicked.connect(self._browse_file)
        source_layout.addWidget(self.source_path)
        source_layout.addWidget(btn_browse_folder)
        source_layout.addWidget(btn_browse_file)
        form_layout.addRow("Source:", source_layout)

        # Archive format
        self.archive_format = QComboBox()
        self.archive_format.addItems(["tar.gz", "zip"])
        form_layout.addRow("Archive Format:", self.archive_format)

        # Options
        self.auto_set_channel = QCheckBox("Set channel target to this version after publish")
        form_layout.addRow("", self.auto_set_channel)

        self.dry_run = QCheckBox("Dry run (build & validate only, no upload)")
        form_layout.addRow("", self.dry_run)

        form_group.setLayout(form_layout)
        content_layout.addWidget(form_group, 2)

        # Right: Actions and output
        right_layout = QVBoxLayout()

        # Action buttons
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()

        self.btn_build = QPushButton("🔨 Build Archive")
        self.btn_build.setMinimumHeight(36)
        self.btn_build.clicked.connect(self._action_build)

        self.btn_compute = QPushButton("🔢 Compute SHA256")
        self.btn_compute.setMinimumHeight(36)
        self.btn_compute.clicked.connect(self._action_compute_sha)

        self.btn_validate = QPushButton("✅ Validate Manifest")
        self.btn_validate.setMinimumHeight(36)
        self.btn_validate.clicked.connect(self._action_validate)

        self.btn_publish = QPushButton("🚀 Upload & Publish")
        self.btn_publish.setMinimumHeight(44)
        self.btn_publish.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white;")
        self.btn_publish.clicked.connect(self._action_publish)

        self.btn_verify = QPushButton("🔍 Verify on Server")
        self.btn_verify.setMinimumHeight(36)
        self.btn_verify.clicked.connect(self._action_verify)

        actions_layout.addWidget(self.btn_build)
        actions_layout.addWidget(self.btn_compute)
        actions_layout.addWidget(self.btn_validate)
        actions_layout.addWidget(self.btn_publish)
        actions_layout.addWidget(self.btn_verify)

        actions_group.setLayout(actions_layout)
        right_layout.addWidget(actions_group)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        right_layout.addWidget(self.progress_label)

        # Output
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout()
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(200)
        output_layout.addWidget(self.output)
        output_group.setLayout(output_layout)
        right_layout.addWidget(output_group)

        content_layout.addLayout(right_layout, 1)
        layout.addLayout(content_layout)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder:
            self.source_path.setText(folder)

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Archive File", "", "Archives (*.tar.gz *.zip);;All Files (*)"
        )
        if file_path:
            self.source_path.setText(file_path)

    def _validate_inputs(self) -> bool:
        """Validate required inputs."""
        if not self.device_type.currentText().strip():
            QMessageBox.warning(self, "Validation", "Device Type is required")
            return False
        if not self.distribution.currentText().strip():
            QMessageBox.warning(self, "Validation", "Distribution is required")
            return False
        if not self.version.text().strip():
            QMessageBox.warning(self, "Validation", "Version is required")
            return False
        if not self.source_path.text().strip():
            QMessageBox.warning(self, "Validation", "Source path is required")
            return False
        
        # Validate format: alphanumeric, dots, dashes, underscores
        import re
        pattern = r"^[A-Za-z0-9._-]{1,128}$"
        for field, name in [
            (self.device_type.currentText(), "Device Type"),
            (self.distribution.currentText(), "Distribution"),
            (self.version.text(), "Version"),
        ]:
            if not re.match(pattern, field.strip()):
                QMessageBox.warning(self, "Validation", f"{name} contains invalid characters")
                return False

        return True

    def _action_build(self):
        """Build archive from folder."""
        if not self.source_path.text().strip():
            QMessageBox.warning(self, "Error", "Select a source folder first")
            return

        source = Path(self.source_path.text())
        if not source.is_dir():
            QMessageBox.warning(self, "Error", "Source must be a folder to build archive")
            return

        try:
            fmt = self.archive_format.currentText()
            output_name = f"update.{fmt}"
            temp_dir = Path(os.environ.get("TEMP", "/tmp"))
            output_path = temp_dir / output_name

            self.output.append(f"Building archive from {source}...")
            archive_path = build_archive(source, output_path, fmt=fmt)
            self.output.append(f"✅ Archive built: {archive_path}")
            self.source_path.setText(str(archive_path))

        except Exception as e:
            self.output.append(f"❌ Error: {e}")

    def _action_compute_sha(self):
        """Compute SHA256 of selected file."""
        path = self.source_path.text().strip()
        if not path:
            QMessageBox.warning(self, "Error", "Select a file first")
            return

        source = Path(path)
        if not source.is_file():
            QMessageBox.warning(self, "Error", "Source must be a file")
            return

        try:
            self.output.append(f"Computing SHA256 for {source.name}...")
            sha256, size = compute_sha256(source)
            self.output.append(f"✅ SHA256: {sha256}")
            self.output.append(f"✅ Size: {size} bytes")

        except Exception as e:
            self.output.append(f"❌ Error: {e}")

    def _action_validate(self):
        """Validate manifest fields."""
        if not self._validate_inputs():
            return

        source = Path(self.source_path.text())
        if source.is_file():
            sha256, size = compute_sha256(source)
        else:
            sha256, size = "pending", 0

        manifest = build_manifest(
            device_type=self.device_type.currentText().strip(),
            distribution=self.distribution.currentText().strip(),
            version=self.version.text().strip(),
            archive_name=source.name,
            sha256=sha256,
            size=size,
            notes=self.notes.toPlainText(),
        )

        if validate_manifest(manifest):
            self.output.append("✅ Manifest structure is valid")
            self.output.append(f"Preview: {manifest}")
        else:
            self.output.append("❌ Manifest validation failed")

    def _action_publish(self):
        """Upload and publish the release."""
        if not self._validate_inputs():
            return

        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Busy", "A publish operation is already in progress")
            return

        params = {
            "source_path": self.source_path.text().strip(),
            "device_type": self.device_type.currentText().strip(),
            "distribution": self.distribution.currentText().strip(),
            "version": self.version.text().strip(),
            "notes": self.notes.toPlainText(),
            "archive_format": self.archive_format.currentText(),
            "dry_run": self.dry_run.isChecked(),
        }

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_publish.setEnabled(False)
        self.output.append("Starting publish workflow...")

        self.worker = PublishWorker(self.get_api_client(), params)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_publish_finished)
        self.worker.start()

    def _on_progress(self, percent: int, message: str):
        self.progress_bar.setValue(percent)
        self.progress_label.setText(message)
        self.output.append(f"[{percent}%] {message}")

    def _on_publish_finished(self, success: bool, message: str, data: dict):
        self.progress_bar.setVisible(False)
        self.btn_publish.setEnabled(True)

        if success:
            self.output.append(f"✅ {message}")
            if "manifest" in data:
                self.output.append(f"Manifest: {data['manifest']}")
            if "verify_result" in data:
                vr = data["verify_result"]
                self.output.append(f"Verification: manifest={vr.get('manifest_exists')}, archive={vr.get('archive_exists')}")

            # Save to publish history
            self._save_to_history(success, data)

            # Auto-set channel if requested
            if self.auto_set_channel.isChecked() and not self.dry_run.isChecked():
                self._auto_update_channel()
        else:
            self.output.append(f"❌ {message}")
            self._save_to_history(False, {"error": message})

    def _save_to_history(self, success: bool, data: dict):
        """Save publish event to local history."""
        history = load_publish_history()
        events = history.get("events", [])
        events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_type": self.device_type.currentText().strip(),
            "distribution": self.distribution.currentText().strip(),
            "version": self.version.text().strip(),
            "status": "success" if success else "failed",
            "details": data,
        })
        # Keep last 100 events
        history["events"] = events[-100:]
        save_publish_history(history)

    def _auto_update_channel(self):
        """Auto-update channel target version after publish."""
        try:
            api = self.get_api_client()
            channels = api.list_channels()
            device_type = self.device_type.currentText().strip()
            distribution = self.distribution.currentText().strip()
            channel_name = self.channel.text().strip() or "default"
            version = self.version.text().strip()

            # Find matching channel
            for ch in channels.get("items", []):
                if (ch.get("device_type") == device_type and
                    ch.get("distribution") == distribution and
                    ch.get("channel") == channel_name):
                    # Update it
                    api.update_channel(ch["id"], {"target_version": version})
                    self.output.append(f"✅ Channel updated: target_version = {version}")
                    return

            self.output.append(f"⚠️ No matching channel found for auto-update")

        except Exception as e:
            self.output.append(f"⚠️ Auto-update channel failed: {e}")

    def _action_verify(self):
        """Verify artifacts on server."""
        if not self.device_type.currentText() or not self.distribution.currentText() or not self.version.text():
            QMessageBox.warning(self, "Error", "Fill device_type, distribution, and version first")
            return

        try:
            api = self.get_api_client()
            result = api.verify_artifacts(
                self.device_type.currentText().strip(),
                self.distribution.currentText().strip(),
                self.version.text().strip(),
            )
            self.output.append("=== Verification Result ===")
            self.output.append(f"Manifest exists: {result.get('manifest_exists', '?')}")
            self.output.append(f"Archive exists: {result.get('archive_exists', '?')}")
            self.output.append(f"SHA256 match: {result.get('sha256_match', '?')}")
            if result.get("manifest_url"):
                self.output.append(f"Manifest URL: {result['manifest_url']}")
            if result.get("archive_url"):
                self.output.append(f"Archive URL: {result['archive_url']}")
            if result.get("missing_files"):
                self.output.append(f"⚠️ Missing files: {result['missing_files']}")

        except Exception as e:
            self.output.append(f"❌ Verification failed: {e}")

    def _load_device_types(self):
        """Load device types from server and populate the dropdown."""
        try:
            api = self.get_api_client()
            result = api.list_device_types()
            self._device_types_cache = result.get("device_types", {})
            
            # Remember current selection
            current = self.device_type.currentText()
            
            # Clear and repopulate
            self.device_type.clear()
            for dt in sorted(self._device_types_cache.keys()):
                self.device_type.addItem(dt)
            
            # Add "Other..." option
            self.device_type.addItem("── Other (custom) ──")
            
            # Restore selection if it exists
            if current:
                idx = self.device_type.findText(current)
                if idx >= 0:
                    self.device_type.setCurrentIndex(idx)
                else:
                    self.device_type.setEditText(current)
                    
        except Exception as e:
            self.output.append(f"⚠️ Could not load device types: {e}")

    def _on_device_type_changed(self, text: str):
        """When device type changes, update distribution dropdown."""
        if text == "── Other (custom) ──":
            # Clear the text for custom input
            self.device_type.setEditText("")
            self.distribution.clear()
            return
            
        # Populate distributions for this device type
        distributions = self._device_types_cache.get(text, [])
        current_dist = self.distribution.currentText()
        
        self.distribution.clear()
        for dist in sorted(distributions):
            self.distribution.addItem(dist)
        
        # Restore or clear
        if current_dist and current_dist in distributions:
            self.distribution.setCurrentText(current_dist)

    def _get_device_type_text(self) -> str:
        """Get device type text (works with ComboBox)."""
        return self.device_type.currentText().strip()

    def _get_distribution_text(self) -> str:
        """Get distribution text (works with ComboBox)."""
        return self.distribution.currentText().strip()
