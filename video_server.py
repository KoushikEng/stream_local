import asyncio
import sys
import os
import time
import argparse
import ffmpeg
from werkzeug.utils import secure_filename
import random
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageOps  # Added Pillow for image handling

# CHANGED: Import from Quart instead of Flask
from quart import Quart, render_template, send_from_directory, request

parser = argparse.ArgumentParser()
parser.add_argument('dir', nargs='?', type=str)
parser.add_argument('-host', '-u', help="host")
parser.add_argument('-port', '-p', type=int, help="port")
parser.add_argument('--dev', action='store_true')
args = parser.parse_args()

app = Quart(__name__, static_folder="public", static_url_path='')

def handle_win_error_10054(loop, context):
    """
    Suppress specific Windows asyncio errors caused by client disconnects.
    """
    msg = context.get("exception", context["message"])
    # Check for the specific socket error
    if "WinError 10054" in str(msg) or "ConnectionResetError" in str(msg):
        # This is noise. Swallow it.
        return
    
    # If it's a real error, let the default handler scream about it
    loop.default_exception_handler(context)

@app.before_serving
async def startup():
    # Only apply this patch on Windows
    if sys.platform == 'win32':
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(handle_win_error_10054)

# Configure the video directory
VIDEO_DIR = "C:\\Users\\koushik\\Downloads" if not args.dir else args.dir
THUMBNAIL_DIR = os.path.join(os.path.dirname(__file__), "thumbnails")

# Ensure thumbnail directory exists
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

VIDEO_EXTS = ('.mp4', '.ts', '.mkv', '.avi', '.mov', '.webm')
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')

# --- Helper Functions (Keep these synchronous mostly, as they are CPU bound) ---

def get_video_duration(video_path):
    try:
        probe = ffmpeg.probe(video_path)
        return float(probe['format']['duration'])
    except:
        return 10

def generate_video_thumbnail(video_path, thumbnail_path):
    try:
        duration = get_video_duration(video_path)
        random_time = random.uniform(1, max(2, duration-1))
        (
            ffmpeg.input(video_path, ss=str(random_time))
            .output(thumbnail_path, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True, quiet=True)
        )
        return True
    except Exception as e:
        print(f"Error generating video thumbnail {video_path}: {e}")
        return False

def generate_image_thumbnail(image_path, thumbnail_path):
    """
    Efficiently resizes high-res images to thumbnails using Pillow.
    This prevents the browser from choking on 10MB files.
    """
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (e.g. for PNGs with transparency or RGBA)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Create a thumbnail preserving aspect ratio
            # 400x400 is a decent balance for quality vs speed
            img = ImageOps.fit(img, (400, 225), method=Image.Resampling.LANCZOS) 
            img.save(thumbnail_path, "JPEG", quality=80)
        return True
    except Exception as e:
        print(f"Error generating image thumbnail {image_path}: {e}")
        return False

def process_thumbnail_task(file_path, thumb_path, is_video):
    """Wrapper to decide which generator to use"""
    # Only generate if missing or older
    if not os.path.exists(thumb_path) or (os.path.getmtime(file_path) > os.path.getmtime(thumb_path)):
        if is_video:
            return generate_video_thumbnail(file_path, thumb_path)
        else:
            return generate_image_thumbnail(file_path, thumb_path)
    return True

def scan_and_generate_thumbnails():
    """
    This remains synchronous because we run it at startup.
    """
    print("Starting media scan and thumbnail generation...")
    start_time = time.time()
    media_files = []
    
    for root, _, files in os.walk(VIDEO_DIR):
        if "$RECYCLE.BIN" in root: continue
        for file in files:
            lower_file = file.lower()
            is_video = lower_file.endswith(VIDEO_EXTS)
            is_image = lower_file.endswith(IMAGE_EXTS)
            
            if is_video or is_image:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, VIDEO_DIR)
                # Create a safe filename for the thumbnail
                thumb_name = secure_filename(f"{rel_path.replace(os.sep, '_')}.jpg")
                thumb_path = os.path.join(THUMBNAIL_DIR, thumb_name)
                media_files.append((file_path, thumb_path, is_video))
    
    print(f"Found {len(media_files)} media files")
    
    # We can still use ThreadPoolExecutor for CPU bound tasks
    with ThreadPoolExecutor(max_workers=6) as executor:
        # Submit tasks
        futures = [executor.submit(process_thumbnail_task, mf[0], mf[1], mf[2]) for mf in media_files]
        
        # Monitor progress
        completed = 0
        for f in futures:
            f.result()
            completed += 1
            if completed % 50 == 0:
                print(f"Processed {completed}/{len(futures)} thumbnails")
    
    print(f"Generation completed in {time.time() - start_time:.2f} seconds")

def get_folder_contents(folder_path):
    abs_path = os.path.join(VIDEO_DIR, folder_path)
    contents = {'media': [], 'subfolders': set()}

    if not os.path.exists(abs_path):
        return contents

    for item in os.listdir(abs_path):
        item_path = os.path.join(abs_path, item)
        rel_path = os.path.join(folder_path, item)
        
        if os.path.isfile(item_path):
            lower_item = item.lower()
            is_video = lower_item.endswith(VIDEO_EXTS)
            is_image = lower_item.endswith(IMAGE_EXTS)
            
            if is_video or is_image:
                base_name = secure_filename(rel_path.replace(os.sep, '_'))
                media_item = {
                    'name': item,
                    'path': rel_path.replace('\\', '/').replace('\'', '\\\''),
                    'thumbnail': f"/thumbnails/{base_name}.jpg",
                    'type': 'video' if is_video else 'image'
                }
                if is_video:
                    media_item['preview'] = f"/previews/preview_{item}"
                contents['media'].append(media_item)
                
        elif os.path.isdir(item_path):
            # Recursive check: does this folder contain ANY valid media deep down?
            has_media = False
            for root, _, files in os.walk(item_path):
                if "$RECYCLE.BIN" in root: continue
                if any(f.lower().endswith(VIDEO_EXTS + IMAGE_EXTS) for f in files):
                    has_media = True
                    break
            if has_media:
                contents['subfolders'].add(item)

    contents['subfolders'] = sorted(contents['subfolders'])
    contents['media'] = sorted(contents['media'], key=lambda x: x['name'])
    return contents

# --- ROUTES (Converted to Async) ---

@app.route('/')
async def index():
    folder_path = request.args.get('folder', '')
    # get_folder_contents is fast enough to run sync, or could be wrapped in run_in_executor
    # For directory listing, sync is usually fine, but for heavy I/O use aiofiles
    contents = get_folder_contents(folder_path)
    
    breadcrumbs = []
    if folder_path:
        parts = folder_path.split(os.sep)
        for i in range(len(parts)):
            breadcrumbs.append({
                'name': parts[i],
                'path': os.sep.join(parts[:i+1])
            })
    
    # Quart requires await on render_template
    return await render_template('index.html',
                           path=os.path,
                           contents=contents,
                           current_folder=folder_path,
                           breadcrumbs=breadcrumbs)

@app.route('/videos/<path:filename>')
async def serve_video(filename):
    # send_from_directory is async in Quart - this is the KEY fix for blocking
    return await send_from_directory(VIDEO_DIR, filename)

@app.route('/previews/<path:filename>')
async def serve_preview(filename):
    return await send_from_directory('previews', filename)

@app.route('/thumbnails/<filename>')
async def serve_thumbnail(filename):
    return await send_from_directory(THUMBNAIL_DIR, filename)

@app.post('/test')
async def test_route(): # A simple test route to receive data
    data = await request.get_json()
    print("Received data:", data)
    return {'status': 'success', 'received': data}

if __name__ == '__main__':
    # Startup tasks
    if not os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        try:
            from preview import batch_create_previews
            batch_create_previews(VIDEO_DIR, "previews")
        except ImportError:
            print("Warning: Preview generator not found.")
            
        scan_and_generate_thumbnails()
    
    host = '0.0.0.0' if not args.host else args.host
    port = 80 if not args.port else args.port
    
    if args.dev:
        print("=== Running in development mode ===")
        app.run(host=host, port=port, debug=True)
    else:
        print("=== Running in production mode (Uvicorn) ===")
        import uvicorn
        # Note: Uvicorn needs the import string "filename:app_variable"
        # Since we are in the main block, we can run the app instance directly
        uvicorn.run(app, host=host, port=port, log_level="warning")