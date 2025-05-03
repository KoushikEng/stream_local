# Local Video Streaming Server

A minimal Flask-based web application for streaming video files from a local directory to devices on the same network, with Windows/Linux service support.

## Features

- **Cross-Platform Support**: Runs as native service on both Windows and Linux
- **Simple Management**: Unified commands for both platforms (`install`, `start`)
- **Auto-Detection**: Automatically detects OS and applies appropriate service manager
- **Production Ready**: Uses Waitress WSGI server with configurable threads
- **Persistent**: Runs in background and survives reboots (when installed as service)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/koushikEng/minimal-video-stream.git
   cd minimal-video-stream
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

   **Platform-specific dependencies**:
   ```bash
   # Windows only
   pip install pywin32

   # Linux only
   sudo apt-get install systemd
   ```

## Usage

### Server Management

| Command                | Windows                      | Linux                        |
|------------------------|------------------------------|------------------------------|
| Install service        | `python video_service.py install` | `sudo python video_service.py install` |
| Start service          | `python video_service.py start`   | `sudo python video_service.py start`   |
| Check status           | Services MMC                | `sudo systemctl status video_stream_server` |
| View logs              | Event Viewer                | `journalctl -u video_stream_server` |

### Configuration Options

```bash
# Install with custom port and threads
python video_service.py install --port 8080 --threads 8

# Available parameters:
#   --port     Server port (default: 5000)
#   --threads  Worker threads (default: 4)
```

### Direct Server Execution

```bash
# Development mode
python video_server.py [directory_path]

# Production mode
python video_server.py [directory_path] --prod

# Set host and port (default to 0.0.0.0 5000)
python video_server.py [directory_path] -host [host] -port [port]
```

## Service Details

### Windows Service
- Installs via Windows Service Control Manager
- Runs under Local System account
- Automatic recovery on failure
- Managed through `services.msc`

### Linux Service
- Creates systemd unit file at `/etc/systemd/system/video_stream_server.service`
- Runs under current user account
- Automatic restart on failure
- Logs via journald

## File Structure

```
local-video-streamer/
├── video_server.py         # Main application
├── video_service.py        # Cross-platform service manager
├── templates/
│   └── index.html          # Web interface
├── README.md               # This document
└── requirements.txt        # Dependencies
```

## Troubleshooting

**Service fails to start**:
1. Check logs (Windows: Event Viewer, Linux: `journalctl -u video_stream_server`)
2. Verify port is available (`netstat -tulnp | grep <port>`)
3. Check firewall rules

**Permission issues on Linux**:
```bash
# Set proper permissions
sudo chmod 644 /etc/systemd/system/video_stream_server.service
sudo systemctl daemon-reload
```

**Missing dependencies**:
```bash
# Windows
pip install pywin32

# Linux
sudo apt install python3-systemd
```

## Security Notes

1. The server binds to all interfaces (`0.0.0.0`) by default
2. For production use:
   - Consider adding authentication
   - Use HTTPS with reverse proxy (Nginx/Apache)
   - Restrict access to local network

## License

MIT License - Free for personal and commercial use
