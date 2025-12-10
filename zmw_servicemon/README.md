# service_mon

Monitors all other running z2m services, tracks their status (up/down), and monitors systemd journal for errors. Provides a dashboard view of system health.

## WWW Endpoints

- `/ls` - List all known services with metadata and status
- `/systemd_status` - HTML-formatted systemd status output
- `/recent_errors` - Recent errors from journal monitor
