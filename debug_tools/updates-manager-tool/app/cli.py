"""Updates Manager Tool - Command Line Interface.

Usage:
    python -m app.cli list-channels
    python -m app.cli verify --device-type rpi4 --distribution stable --version 1.0.0
    python -m app.cli publish --device-type rpi4 --distribution stable --version 1.0.0 --source ./build
    python -m app.cli fleet --state OUTDATED
    python -m app.cli history --device-key abc123
    python -m app.cli register --device-key <key> --token-code <token>
    python -m app.cli status
    python -m app.cli check-update
    python -m app.cli self-update
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .api_client import ApiClient, ApiConfig
from .device_manager import DeviceManager
from .publisher import build_archive, build_manifest, compute_sha256, write_manifest
from .settings import get_token
from .storage import load_profiles
from .version import __version__


def build_client(profile: str | None) -> ApiClient:
    profiles = load_profiles()
    prof = None
    if profile:
        for p in profiles.get("profiles", []):
            if p.get("name") == profile:
                prof = p
                break
    else:
        active = profiles.get("active")
        for p in profiles.get("profiles", []):
            if p.get("name") == active:
                prof = p
                break

    if not prof:
        raise SystemExit("No profile configured. Use the GUI Settings first or set MEETING_TOKEN env var.")

    token = get_token(prof.get("name", "")) or os.environ.get("MEETING_TOKEN")
    cfg = ApiConfig(
        base_url=prof.get("base_url", ""),
        token=token,
        timeout=int(prof.get("timeout", 20)),
        retries=int(prof.get("retries", 3)),
    )
    return ApiClient(cfg)


def cmd_list_channels(args, client: ApiClient):
    """List all update channels."""
    data = client.list_channels()
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        items = data.get("items", [])
        print(f"Found {len(items)} channels:\n")
        for ch in items:
            active = "✅" if ch.get("active") else "❌"
            print(f"  {active} {ch.get('device_type')}/{ch.get('distribution')}/{ch.get('channel')} → v{ch.get('target_version', '?')}")


def cmd_verify(args, client: ApiClient):
    """Verify artifacts on server."""
    result = client.verify_artifacts(args.device_type, args.distribution, args.version)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Verification for {args.device_type}/{args.distribution} v{args.version}:")
        print(f"  Manifest exists: {result.get('manifest_exists', '?')}")
        print(f"  Archive exists: {result.get('archive_exists', '?')}")
        print(f"  SHA256 match: {result.get('sha256_match', '?')}")
        if result.get("missing_files"):
            print(f"  ⚠️ Missing: {result['missing_files']}")


def cmd_publish(args, client: ApiClient):
    """Publish a release."""
    source_path = Path(args.source)
    
    if not source_path.exists():
        raise SystemExit(f"Source not found: {source_path}")

    print(f"Publishing {args.device_type}/{args.distribution} v{args.version}...")

    # Build archive if source is a directory
    if source_path.is_dir():
        print("  Building archive from folder...")
        fmt = args.format or "tar.gz"
        archive_name = f"update.{fmt}"
        temp_dir = Path(os.environ.get("TEMP", "/tmp"))
        archive_path = temp_dir / f"{args.device_type}_{args.distribution}_{args.version}_{archive_name}"
        build_archive(source_path, archive_path, fmt=fmt)
    else:
        archive_path = source_path
        archive_name = source_path.name

    # Compute SHA256
    print("  Computing SHA256...")
    sha256, size = compute_sha256(archive_path)
    print(f"  SHA256: {sha256}")
    print(f"  Size: {size} bytes")

    # Build manifest
    print("  Building manifest...")
    manifest = build_manifest(
        device_type=args.device_type,
        distribution=args.distribution,
        version=args.version,
        archive_name=archive_name,
        sha256=sha256,
        size=size,
        notes=args.notes or "",
    )
    manifest_path = archive_path.parent / "manifest.json"
    write_manifest(manifest_path, manifest)

    if args.dry_run:
        print("\n  [DRY RUN] Would upload:")
        print(f"    Manifest: {manifest_path}")
        print(f"    Archive: {archive_path}")
        return

    # Upload
    print("  Uploading...")
    with open(manifest_path, "rb") as mf, open(archive_path, "rb") as af:
        files = {
            "manifest": ("manifest.json", mf, "application/json"),
            "archive": (archive_name, af, "application/octet-stream"),
        }
        data = {
            "device_type": args.device_type,
            "distribution": args.distribution,
            "version": args.version,
        }
        result = client.publish_update(files, data=data)

    print("  ✅ Published successfully!")
    if args.json:
        print(json.dumps(result, indent=2))

    # Verify
    print("  Verifying...")
    verify = client.verify_artifacts(args.device_type, args.distribution, args.version)
    if verify.get("manifest_exists") and verify.get("archive_exists"):
        print("  ✅ Verification passed")
    else:
        print("  ⚠️ Verification failed - check server logs")


def cmd_fleet(args, client: ApiClient):
    """List fleet status."""
    params = {"page": args.page, "page_size": args.page_size}
    if args.state:
        params["state"] = args.state
    if args.device_type:
        params["device_type"] = args.device_type
    if args.search:
        params["search"] = args.search

    data = client.list_device_updates(params)
    
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        items = data.get("items", [])
        total = data.get("total", len(items))
        print(f"Fleet status (showing {len(items)} of {total}):\n")
        for dev in items:
            state = dev.get("computed_state", "?")
            icon = {"UP_TO_DATE": "✅", "OUTDATED": "⚠️", "FAILING": "❌"}.get(state, "❓")
            print(f"  {icon} {dev.get('device_key', '?')[:20]}... | {dev.get('device_type')} | v{dev.get('installed_version', '?')} → v{dev.get('target_version', '?')}")


def cmd_history(args, client: ApiClient):
    """List update history."""
    params = {"page": args.page, "page_size": args.page_size}
    if args.device_key:
        params["device_key"] = args.device_key
    if args.status:
        params["status"] = args.status

    data = client.list_update_history(params)
    
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        items = data.get("items", [])
        total = data.get("total", len(items))
        print(f"Update history (showing {len(items)} of {total}):\n")
        for rec in items:
            status = rec.get("status", "?")
            icon = {"success": "✅", "failed": "❌", "pending": "⏳"}.get(status, "❓")
            ts = rec.get("created_at", "?")[:19]
            print(f"  {icon} {ts} | {rec.get('device_key', '?')[:15]}... | v{rec.get('target_version', '?')} | {status}")


def cmd_register(args):
    """Register device with Meeting server."""
    import requests
    
    device_key = args.device_key
    token_code = args.token_code.upper()
    server_url = args.server or "https://meeting.ygsoft.fr"
    
    print(f"Registering device with Meeting server...")
    print(f"  Server: {server_url}")
    print(f"  Device Key: {device_key[:8]}...{device_key[-4:]}")
    print(f"  Token Code: {token_code}")
    print()
    
    try:
        # Send heartbeat to verify registration
        response = requests.post(
            f"{server_url}/api/devices/{device_key}/online",
            json={
                "note": "Updates Manager Tool - CLI registration",
                "token_code": token_code,
            },
            timeout=15,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                # Save registration
                dm = DeviceManager()
                dm.save_device_key(device_key, token_code, server_url)
                print("✅ Registration successful!")
                print(f"  Last seen: {data.get('last_seen')}")
                print(f"  Credentials saved to: {dm.device_file}")
                return 0
            else:
                print(f"❌ Registration failed: {data.get('message')}")
                return 1
        elif response.status_code == 404:
            print("❌ Device not found on server")
            print("   Make sure the device_key exists in Meeting admin")
            return 1
        else:
            print(f"❌ Server error: {response.status_code}")
            return 1
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to {server_url}")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_status(args):
    """Show current device registration status."""
    dm = DeviceManager()
    dm.load_device_key()
    
    print(f"Updates Manager Tool v{__version__}")
    print("=" * 40)
    print()
    
    if dm.is_registered():
        print("✅ Device is REGISTERED")
        print()
        print(f"  Device Key: {dm.device_key[:8]}...{dm.device_key[-4:]}")
        print(f"  Token Code: {'•' * 6}")
        print(f"  Server URL: {dm.server_url}")
        print(f"  Config file: {dm.device_file}")
        
        if args.json:
            print()
            print(json.dumps({
                "registered": True,
                "device_key": dm.device_key,
                "server_url": dm.server_url,
                "config_file": str(dm.device_file),
            }, indent=2))
    else:
        print("❌ Device is NOT REGISTERED")
        print()
        print("To register, use:")
        print("  cli.py register --device-key <key> --token-code <code>")
        
        if args.json:
            print()
            print(json.dumps({"registered": False}, indent=2))
    
    return 0


def cmd_check_update(args):
    """Check for available updates."""
    from .updater import Updater
    
    print(f"Checking for updates...")
    print(f"  Current version: {__version__}")
    print()
    
    try:
        updater = Updater()
        update_info = updater.check_for_update(
            distribution=args.distribution,
            channel=args.channel,
        )
        
        if update_info:
            print(f"✅ Update available!")
            print(f"  New version: {update_info.version}")
            print(f"  Download URL: {update_info.download_url}")
            if update_info.sha256:
                print(f"  SHA256: {update_info.sha256}")
            if update_info.release_notes:
                print(f"\nRelease notes:\n{update_info.release_notes}")
            
            if args.json:
                print()
                print(json.dumps({
                    "update_available": True,
                    "current_version": __version__,
                    "new_version": update_info.version,
                    "download_url": update_info.download_url,
                    "sha256": update_info.sha256,
                }, indent=2))
            return 0
        else:
            print("✅ You are up to date!")
            if args.json:
                print()
                print(json.dumps({
                    "update_available": False,
                    "current_version": __version__,
                }, indent=2))
            return 0
            
    except Exception as e:
        print(f"❌ Error checking for updates: {e}")
        return 1


def cmd_self_update(args):
    """Download and install available update."""
    from .updater import Updater
    
    print(f"Self-update process starting...")
    print(f"  Current version: {__version__}")
    print()
    
    try:
        updater = Updater()
        update_info = updater.check_for_update(
            distribution=args.distribution,
            channel=args.channel,
        )
        
        if not update_info:
            print("✅ Already up to date!")
            return 0
        
        print(f"Found update: v{update_info.version}")
        
        if not args.yes:
            confirm = input("Do you want to download and install? [y/N] ")
            if confirm.lower() != 'y':
                print("Cancelled.")
                return 0
        
        # Download
        print(f"\nDownloading...")
        
        def progress(downloaded, total):
            if total > 0:
                pct = int((downloaded / total) * 100)
                bar = '█' * (pct // 5) + '░' * (20 - pct // 5)
                print(f"\r  [{bar}] {pct}% ({downloaded // 1024} KB)", end='', flush=True)
        
        download_path = updater.download_update(update_info, progress)
        print()  # newline after progress
        
        if not download_path:
            print("❌ Download failed")
            return 1
        
        print(f"✅ Downloaded to: {download_path}")
        
        # Apply update
        print("\nApplying update...")
        success, message = updater.apply_update(download_path, restart=not args.no_restart)
        
        if success:
            print(f"✅ {message}")
            print("\nThe application will now exit for update installation.")
            return 0
        else:
            print(f"❌ {message}")
            return 1
            
    except Exception as e:
        print(f"❌ Error during self-update: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Updates Manager Tool CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list-channels
  %(prog)s verify --device-type rpi4 --distribution stable --version 1.0.0
  %(prog)s publish --device-type rpi4 --distribution stable --version 1.0.0 --source ./build
  %(prog)s fleet --state OUTDATED
  %(prog)s history --device-key abc123
  %(prog)s register --device-key <key> --token-code <code>
  %(prog)s status
  %(prog)s check-update
  %(prog)s self-update --yes
        """
    )
    parser.add_argument("--profile", help="Profile name (uses active profile if not specified)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    sub = parser.add_subparsers(dest="cmd", help="Commands")

    # register
    register_p = sub.add_parser("register", help="Register device with Meeting server")
    register_p.add_argument("--device-key", required=True, help="Device key from Meeting admin")
    register_p.add_argument("--token-code", required=True, help="6-character token code")
    register_p.add_argument("--server", default="https://meeting.ygsoft.fr", help="Meeting server URL")

    # status
    status_p = sub.add_parser("status", help="Show device registration status")

    # check-update
    check_p = sub.add_parser("check-update", help="Check for available updates")
    check_p.add_argument("--distribution", default="stable", help="Distribution (default: stable)")
    check_p.add_argument("--channel", default="default", help="Channel (default: default)")

    # self-update
    selfupdate_p = sub.add_parser("self-update", help="Download and install available update")
    selfupdate_p.add_argument("--distribution", default="stable", help="Distribution (default: stable)")
    selfupdate_p.add_argument("--channel", default="default", help="Channel (default: default)")
    selfupdate_p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    selfupdate_p.add_argument("--no-restart", action="store_true", help="Don't restart after update")

    # list-channels
    sub.add_parser("list-channels", help="List all update channels")

    # verify
    verify_p = sub.add_parser("verify", help="Verify artifacts on server")
    verify_p.add_argument("--device-type", required=True)
    verify_p.add_argument("--distribution", required=True)
    verify_p.add_argument("--version", required=True)

    # publish
    publish_p = sub.add_parser("publish", help="Publish a release")
    publish_p.add_argument("--device-type", required=True)
    publish_p.add_argument("--distribution", required=True)
    publish_p.add_argument("--version", required=True)
    publish_p.add_argument("--source", required=True, help="Source folder or archive file")
    publish_p.add_argument("--notes", help="Release notes")
    publish_p.add_argument("--format", choices=["tar.gz", "zip"], default="tar.gz")
    publish_p.add_argument("--dry-run", action="store_true", help="Don't upload, just build")

    # fleet
    fleet_p = sub.add_parser("fleet", help="List fleet status")
    fleet_p.add_argument("--state", choices=["UP_TO_DATE", "OUTDATED", "FAILING", "UNKNOWN"])
    fleet_p.add_argument("--device-type")
    fleet_p.add_argument("--search", help="Search device keys")
    fleet_p.add_argument("--page", type=int, default=1)
    fleet_p.add_argument("--page-size", type=int, default=20)

    # history
    history_p = sub.add_parser("history", help="List update history")
    history_p.add_argument("--device-key")
    history_p.add_argument("--status", choices=["success", "failed", "pending", "in_progress"])
    history_p.add_argument("--page", type=int, default=1)
    history_p.add_argument("--page-size", type=int, default=20)

    args = parser.parse_args()

    if not args.cmd:
        parser.print_help()
        return

    # Commands that don't need API client
    if args.cmd == "register":
        return cmd_register(args)
    elif args.cmd == "status":
        return cmd_status(args)
    elif args.cmd == "check-update":
        return cmd_check_update(args)
    elif args.cmd == "self-update":
        return cmd_self_update(args)

    # Commands that need API client
    try:
        client = build_client(args.profile)
    except SystemExit as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    commands = {
        "list-channels": cmd_list_channels,
        "verify": cmd_verify,
        "publish": cmd_publish,
        "fleet": cmd_fleet,
        "history": cmd_history,
    }

    try:
        commands[args.cmd](args, client)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
