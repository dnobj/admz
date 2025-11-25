#!/usr/bin/env python3
"""
Axis Secrets Web UI - Flask application for managing cameras and accounts.

Usage:
    python web_ui/app.py

Then open: http://localhost:5000
"""

from flask import Flask, render_template, request, redirect, url_for, flash
import os
from axis_secrets import create_camera_registry
from axis_secrets.exceptions import (
    CameraNotFoundError,
    AccountNotFoundError,
    BackendError,
    AuthenticationError,
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

# Initialize registry
try:
    registry = create_camera_registry()
except AuthenticationError as e:
    print(f"ERROR: Failed to connect to Vault: {e}")
    print("\nMake sure environment variables are set:")
    print("  export VAULT_ADDR='http://127.0.0.1:8200'")
    print("  export VAULT_TOKEN='myroot'")
    exit(1)


@app.route("/")
def index():
    """Home page - list all cameras."""
    try:
        cameras = registry.list_cameras()
        return render_template("index.html", cameras=cameras)
    except Exception as e:
        flash(f"Error loading cameras: {e}", "danger")
        return render_template("index.html", cameras=[])


@app.route("/camera/<camera_id>")
def camera_detail(camera_id):
    """Camera detail page - show device info and accounts."""
    try:
        device_info = registry.get_device_info(camera_id)
        accounts = registry.list_accounts(camera_id)
        return render_template(
            "camera_detail.html",
            camera_id=camera_id,
            device_info=device_info,
            accounts=accounts,
        )
    except CameraNotFoundError:
        flash(f"Camera '{camera_id}' not found", "danger")
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"Error loading camera: {e}", "danger")
        return redirect(url_for("index"))


@app.route("/camera/add", methods=["GET", "POST"])
def add_camera():
    """Add a new camera."""
    if request.method == "POST":
        try:
            camera_id = request.form.get("camera_id")

            # Build device info from form
            device_info = {
                "host": request.form.get("host"),
                "ip_address": request.form.get("ip_address"),
                "serial_number": request.form.get("serial_number", ""),
                "mac_address": request.form.get("mac_address", ""),
                "firmware_version": request.form.get("firmware_version", ""),
                "model": request.form.get("model", ""),
                "warranty_expiration": request.form.get("warranty_expiration", ""),
                "location": request.form.get("location", ""),
                "tags": request.form.get("tags", ""),
            }

            # Remove empty values
            device_info = {k: v for k, v in device_info.items() if v}

            # Add camera (without accounts for now)
            registry.add_camera(camera_id, device_info)

            flash(f"Camera '{camera_id}' added successfully!", "success")
            return redirect(url_for("camera_detail", camera_id=camera_id))

        except BackendError as e:
            flash(f"Error adding camera: {e}", "danger")
        except Exception as e:
            flash(f"Unexpected error: {e}", "danger")

    return render_template("add_camera.html")


@app.route("/camera/<camera_id>/add-account", methods=["GET", "POST"])
def add_account(camera_id):
    """Add an account to a camera."""
    if request.method == "POST":
        try:
            account_id = request.form.get("account_id")

            account_data = {
                "username": request.form.get("username"),
                "password": request.form.get("password"),
                "account_type": request.form.get("account_type", "service"),
                "purpose": request.form.get("purpose", ""),
                "permissions": request.form.get("permissions", ""),
            }

            # Remove empty values
            account_data = {k: v for k, v in account_data.items() if v}

            registry.add_account(camera_id, account_id, account_data)

            flash(f"Account '{account_id}' added successfully!", "success")
            return redirect(url_for("camera_detail", camera_id=camera_id))

        except CameraNotFoundError:
            flash(f"Camera '{camera_id}' not found", "danger")
            return redirect(url_for("index"))
        except BackendError as e:
            flash(f"Error adding account: {e}", "danger")
        except Exception as e:
            flash(f"Unexpected error: {e}", "danger")

    try:
        device_info = registry.get_device_info(camera_id)
        return render_template(
            "add_account.html",
            camera_id=camera_id,
            device_info=device_info,
        )
    except CameraNotFoundError:
        flash(f"Camera '{camera_id}' not found", "danger")
        return redirect(url_for("index"))


@app.route("/camera/<camera_id>/account/<account_id>/credentials")
def view_credentials(camera_id, account_id):
    """View credentials for an account (shows password)."""
    try:
        creds = registry.get_credentials(camera_id, account_id)
        device_info = registry.get_device_info(camera_id)

        return render_template(
            "view_credentials.html",
            camera_id=camera_id,
            account_id=account_id,
            credentials=creds,
            device_info=device_info,
        )
    except (CameraNotFoundError, AccountNotFoundError) as e:
        flash(str(e), "danger")
        return redirect(url_for("index"))
    except Exception as e:
        flash(f"Error retrieving credentials: {e}", "danger")
        return redirect(url_for("index"))


@app.route("/camera/<camera_id>/delete", methods=["POST"])
def delete_camera(camera_id):
    """Delete a camera."""
    try:
        registry.remove_camera(camera_id)
        flash(f"Camera '{camera_id}' deleted successfully", "success")
    except CameraNotFoundError:
        flash(f"Camera '{camera_id}' not found", "danger")
    except Exception as e:
        flash(f"Error deleting camera: {e}", "danger")

    return redirect(url_for("index"))


@app.route("/camera/<camera_id>/account/<account_id>/delete", methods=["POST"])
def delete_account(camera_id, account_id):
    """Delete an account."""
    try:
        registry.remove_account(camera_id, account_id)
        flash(f"Account '{account_id}' deleted successfully", "success")
    except (CameraNotFoundError, AccountNotFoundError) as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"Error deleting account: {e}", "danger")

    return redirect(url_for("camera_detail", camera_id=camera_id))


@app.route("/health")
def health():
    """Health check endpoint."""
    try:
        cameras = registry.list_cameras()
        return {
            "status": "healthy",
            "vault_connected": True,
            "camera_count": len(cameras),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 500


if __name__ == "__main__":
    print("=" * 70)
    print("Axis Secrets Web UI")
    print("=" * 70)
    print(f"\nVault Address: {os.getenv('VAULT_ADDR', 'Not set!')}")
    print(f"Vault Token: {'Set' if os.getenv('VAULT_TOKEN') else 'Not set!'}")
    print("\nStarting web server...")
    print("Open your browser to: http://localhost:5000")
    print("\nPress Ctrl+C to stop")
    print("=" * 70)

    app.run(debug=True, host="0.0.0.0", port=5000)
