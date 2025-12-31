import argparse
from config import set_media_dir

parser = argparse.ArgumentParser("StreamLocal - Local Media Streaming Server")
parser.add_argument('dir', nargs='?', type=str)
parser.add_argument('--host', '-u', default='0.0.0.0', help="Host to run on (default: 0.0.0.0)")
parser.add_argument('--port', '-p', type=int, default=80, help="Port to run on (default: 80)")
parser.add_argument('--dev', action='store_true')
parser.add_argument('--no-preprocessing', action='store_true')
args = parser.parse_args()

set_media_dir(args.dir)

from config import MEDIA_DIR, THUMBNAIL_DIR, PREVIEW_DIR, VIDEO_EXTS, IMAGE_EXTS
from server import app

from librifygen.config import set_extensions
set_extensions(VIDEO_EXTS, IMAGE_EXTS)

if __name__ == '__main__':
    print("Starting StreamLocal...")
    
    # Startup tasks
    if not args.no_preprocessing:
        try:
            from librifygen import generate_previews, generate_thumbnails
            
            generate_previews(MEDIA_DIR, PREVIEW_DIR)
            generate_thumbnails(MEDIA_DIR, THUMBNAIL_DIR)
            
        except ImportError:
            print("Warning: Preview generator not found.")
        except Exception as e:
            print(f"Error during preprocessing: {e}")
    else:
        print("Skipping preprocessing.")
    
    HOST =  args.host
    PORT = args.port
    
    if args.dev:
        print("=== Running in development mode ===")
        app.run(host=HOST, port=PORT, debug=True)
    else:
        print("=== Running in production mode (Uvicorn) ===")
        import uvicorn
        # Note: Uvicorn needs the import string "filename:app_variable"
        # Since we are in the main block, we can run the app instance directly
        uvicorn.run(app, host=HOST, port=PORT, log_level="warning")