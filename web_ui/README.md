# Axis Secrets Web UI

A Flask-based web interface for managing Axis camera credentials and device information.

## Features

- 📋 **List all cameras** with device information
- 🔍 **View camera details** including all accounts
- ➕ **Add new cameras** with complete device catalog
- 👤 **Manage accounts** for each camera
- 🔐 **View credentials** securely (with copy-to-clipboard)
- 🗑️ **Delete cameras and accounts**
- 🎨 **Clean Bootstrap UI** with responsive design

## Quick Start

### 1. Make sure Vault is running

```bash
# Check Vault is accessible
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='myroot'
vault status
```

### 2. Install dependencies

```bash
# Install Flask (if not already installed)
pip install -r requirements.txt
# Or just Flask:
pip install flask>=3.0.0
```

### 3. Start the web server

```bash
python web_ui/app.py
```

### 4. Open your browser

Navigate to: **http://localhost:5000**

## Screenshots

### Home Page
Lists all cameras with quick access to details and delete actions.

### Camera Detail
Shows complete device information and all associated accounts.

### Add Camera
Form to add new camera with all device catalog fields:
- Basic info (host, IP, location)
- Device details (serial, MAC, firmware, model)
- Network configuration (VLAN, subnet)
- Tags and warranty info

### Add Account
Form to add accounts to cameras with:
- Account type (service, admin, viewer)
- Credentials (username, password)
- Password generator
- Purpose and permissions

### View Credentials
Secure view of credentials with:
- Show/hide password toggle
- Copy-to-clipboard buttons
- Quick connect examples (curl, Python, RTSP)

## Security Notes

⚠️ **Important Security Considerations:**

1. **Production Use**
   - Set a strong `FLASK_SECRET_KEY` environment variable
   - Enable HTTPS (use nginx/apache as reverse proxy)
   - Restrict network access to trusted users only
   - Use proper authentication (add login system)

2. **Vault Token**
   - The web UI uses the Vault token from environment
   - In production, use AppRole authentication
   - Consider short-lived tokens with renewal

3. **Password Display**
   - Credentials page shows passwords in plain text
   - Add audit logging for credential access
   - Consider requiring additional authentication

## Configuration

### Environment Variables

```bash
# Required
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='myroot'
# Or use AppRole:
export VAULT_ROLE_ID='your-role-id'
export VAULT_SECRET_ID='your-secret-id'

# Optional
export FLASK_SECRET_KEY='your-secret-key'  # For production
export FLASK_ENV='development'              # Or 'production'
```

### Custom Port

```python
# In app.py, change:
app.run(debug=True, host="0.0.0.0", port=5000)
# To your preferred port
```

## API Endpoints

The web UI provides these routes:

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Home page (camera list) |
| `/camera/<id>` | GET | Camera detail page |
| `/camera/add` | GET, POST | Add new camera |
| `/camera/<id>/add-account` | GET, POST | Add account to camera |
| `/camera/<id>/account/<account>/credentials` | GET | View credentials |
| `/camera/<id>/delete` | POST | Delete camera |
| `/camera/<id>/account/<account>/delete` | POST | Delete account |
| `/health` | GET | Health check (JSON) |

## Development

### Running in Debug Mode

```bash
# Debug mode is enabled by default when running directly
python web_ui/app.py
```

Changes to Python files will auto-reload the server.

### File Structure

```
web_ui/
├── app.py                    # Flask application
├── templates/                # HTML templates
│   ├── base.html            # Base template with navigation
│   ├── index.html           # Camera list page
│   ├── camera_detail.html   # Camera detail page
│   ├── add_camera.html      # Add camera form
│   ├── add_account.html     # Add account form
│   └── view_credentials.html # Credentials display
├── static/                   # Static files (currently empty)
└── README.md                # This file
```

## Customization

### Styling

The UI uses Bootstrap 5 and Bootstrap Icons CDN. To customize:

1. Add custom CSS in `static/custom.css`
2. Include in `base.html`:
   ```html
   <link rel="stylesheet" href="{{ url_for('static', filename='custom.css') }}">
   ```

### Adding Features

Common additions:

- **Authentication**: Add Flask-Login for user authentication
- **Authorization**: Role-based access control (admin vs viewer)
- **Audit Logging**: Log all credential access
- **Search/Filter**: Add search box for cameras
- **Bulk Operations**: Import/export cameras via CSV
- **Password Rotation**: Trigger password rotation from UI

## Troubleshooting

### "Vault address not configured"

```bash
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='myroot'
```

### "Connection refused"

- Make sure Vault is running: `docker ps` or `vault status`
- Check VAULT_ADDR points to correct host/port

### "Permission denied"

- Check Vault token has appropriate policies
- For write operations, need `camera-admin` policy

### "Template not found"

- Ensure you're running from the project root: `python web_ui/app.py`
- Check `templates/` directory exists with all .html files

## Production Deployment

### Using Gunicorn (Recommended)

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
cd /path/to/AxisSecrets
gunicorn -w 4 -b 0.0.0.0:5000 'web_ui.app:app'
```

### Using Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name cameras.example.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["python", "web_ui/app.py"]
```

## Support

For issues with the web UI:
- Check `web_ui/app.py` logs for errors
- Verify Vault connectivity
- See main project issues: https://github.com/yourusername/axis-secrets/issues
