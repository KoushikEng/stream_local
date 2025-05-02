import sys
import os
import argparse
import logging
from video_server import app
from waitress import serve

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ServiceManager:
    def __init__(self):
        self.is_windows = sys.platform.startswith('win')
        self.service_name = "video_stream_server"
        self.description = "Local Video Streaming Server"
        self.port = 5000
        self.threads = 4

    def install(self):
        """Install the service for the current platform"""
        if self.is_windows:
            self._install_windows()
        else:
            self._install_linux()

    def start(self):
        """Start the service for the current platform"""
        if self.is_windows:
            self._start_windows()
        else:
            self._start_linux()

    def _install_windows(self):
        """Windows-specific service installation"""
        try:
            import win32serviceutil
            class VideoStreamService(win32serviceutil.ServiceFramework):
                _svc_name_ = self.service_name
                _svc_display_name_ = self.description
                
                def __init__(self, args):
                    win32serviceutil.ServiceFramework.__init__(self, args)
                    self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
                
                def SvcStop(self):
                    self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                    win32event.SetEvent(self.hWaitStop)
                
                def SvcDoCommand(self):
                    serve(app, host='0.0.0.0', port=self.port, threads=self.threads)

            win32serviceutil.HandleCommandLine(VideoStreamService)
            logger.info("Windows service installed successfully")
        except ImportError:
            logger.error("pywin32 not installed. Please install it with: pip install pywin32")
        except Exception as e:
            logger.error(f"Windows service installation failed: {str(e)}")

    def _install_linux(self):
        """Linux-specific service installation"""
        try:
            service_file = f"""[Unit]
Description={self.description}
After=network.target

[Service]
ExecStart={sys.executable} {os.path.abspath(__file__)} --run
WorkingDirectory={os.path.dirname(os.path.abspath(__file__))}
Restart=always
User={os.getenv('USER')}

[Install]
WantedBy=multi-user.target
"""

            service_path = f"/etc/systemd/system/{self.service_name}.service"
            
            if os.geteuid() != 0:
                logger.error("Linux service installation requires root privileges. Please run with sudo.")
                return

            with open(service_path, 'w') as f:
                f.write(service_file)
            
            os.system('systemctl daemon-reload')
            os.system(f'systemctl enable {self.service_name}')
            logger.info(f"Linux service installed at {service_path}")
            logger.info("Service will start automatically on boot")
        except Exception as e:
            logger.error(f"Linux service installation failed: {str(e)}")

    def _start_windows(self):
        """Windows-specific service start"""
        try:
            import win32serviceutil
            win32serviceutil.StartService(self.service_name)
            logger.info("Windows service started successfully")
        except Exception as e:
            logger.error(f"Failed to start Windows service: {str(e)}")

    def _start_linux(self):
        """Linux-specific service start"""
        try:
            if os.geteuid() != 0:
                logger.error("Starting service requires root privileges. Please run with sudo.")
                return
            
            os.system(f'systemctl start {self.service_name}')
            logger.info("Linux service started successfully")
        except Exception as e:
            logger.error(f"Failed to start Linux service: {str(e)}")

    def run_server(self):
        """Directly run the server (used by Linux service)"""
        logger.info(f"Starting video server on port {self.port} with {self.threads} threads")
        serve(app, host='0.0.0.0', port=self.port, threads=self.threads)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Video Stream Server Service Manager')
    parser.add_argument('command', choices=['install', 'start', 'run'], nargs='?', help='Service command')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
    parser.add_argument('--threads', type=int, default=4, help='Number of server threads')
    parser.add_argument('--run', action='store_true', help=argparse.SUPPRESS)  # Internal use for Linux service
    
    args = parser.parse_args()
    
    manager = ServiceManager()
    manager.port = args.port
    manager.threads = args.threads

    if args.run:
        manager.run_server()
    elif args.command == 'install':
        manager.install()
    elif args.command == 'start':
        manager.start()
    else:
        print("Usage:")
        print("  Install service: python video_service.py install")
        print("  Start service:   python video_service.py start")
        print("  Run directly:    python video_service.py run")
        print("\nOptions:")
        print("  --port PORT     Set server port (default: 5000)")
        print("  --threads N     Set server threads (default: 4)")