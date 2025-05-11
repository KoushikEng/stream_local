import os
import time
from flask import Flask, render_template, send_from_directory, request
import ffmpeg
from werkzeug.utils import secure_filename
from concurrent.futures import ThreadPoolExecutor
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('dir', nargs='?', type=str)
parser.add_argument('-host', '-u', help="host")
parser.add_argument('-port', '-p', type=int, help="port")
parser.add_argument('--prod', action='store_true')
args = parser.parse_args()

app = Flask(__name__, static_folder="public", static_url_path='')

# Configure the video directory
VIDEO_DIR = "C:\\Users\\koushik\\Downloads" if not args.dir else args.dir
THUMBNAIL_DIR = os.path.join(os.path.dirname(__file__), "thumbnails")
PREVIEW_DIR = os.path.join(os.path.dirname(__file__), "previews")
THUMBNAIL_WIDTH = 320
PREVIEW_SECONDS = 3  # Duration of preview clips
PREVIEW_WIDTH = 400  # Width of preview videos

# Ensure directories exist
os.makedirs(THUMBNAIL_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)

def generate_thumbnail(video_path, thumbnail_path):
    try:
        (
            ffmpeg.input(video_path, ss='00:00:01')
            .filter('scale', THUMBNAIL_WIDTH, -1)
            .output(thumbnail_path, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True, quiet=True)
        )
        return True
    except ffmpeg.Error as e:
        print(f"Thumbnail error for {video_path}: {e.stderr.decode()}")
        return False

def generate_preview(video_path, preview_path):
    try:
        (
            ffmpeg.input(video_path, ss='00:00:00', t=PREVIEW_SECONDS)
            .filter('scale', PREVIEW_WIDTH, -1)
            .output(preview_path, crf=30, preset='fast', movflags='faststart')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True, quiet=True)
        )
        return True
    except ffmpeg.Error as e:
        print(f"Preview error for {video_path}: {e.stderr.decode()}")
        return False

def scan_and_generate_assets():
    """Generate both thumbnails and previews at startup"""
    print("Starting asset generation...")
    start_time = time.time()
    video_files = []
    
    # Collect all video files
    for root, _, files in os.walk(VIDEO_DIR):
        for file in files:
            if file.lower().endswith(('.mp4', '.ts', '.mkv', '.avi', '.mov')):
                video_path = os.path.join(root, file)
                rel_path = os.path.relpath(video_path, VIDEO_DIR)
                base_name = secure_filename(rel_path.replace(os.sep, '_'))
                
                thumb_path = os.path.join(THUMBNAIL_DIR, f"{base_name}.jpg")
                preview_path = os.path.join(PREVIEW_DIR, f"{base_name}_preview.mp4")
                
                video_files.append((video_path, thumb_path, preview_path))
    
    print(f"Found {len(video_files)} video files")
    
    # Process in parallel
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = []
        for video_path, thumb_path, preview_path in video_files:
            # Generate thumbnail if needed
            if not os.path.exists(thumb_path) or os.path.getmtime(video_path) > os.path.getmtime(thumb_path):
                futures.append(executor.submit(generate_thumbnail, video_path, thumb_path))
            
            # Generate preview if needed
            if not os.path.exists(preview_path) or os.path.getmtime(video_path) > os.path.getmtime(preview_path):
                futures.append(executor.submit(generate_preview, video_path, preview_path))
        
        # Show progress
        for i, future in enumerate(futures, 1):
            future.result()
            if i % 10 == 0 or i == len(futures):
                print(f"Processed {i}/{len(futures)} assets")
    
    print(f"Asset generation completed in {time.time() - start_time:.2f} seconds")

def get_folder_contents(folder_path):
    abs_path = os.path.join(VIDEO_DIR, folder_path)
    
    contents = {
        'videos': [],
        'subfolders': set()
    }

    for item in os.listdir(abs_path):
        item_path = os.path.join(abs_path, item)
        rel_path = os.path.join(folder_path, item)
        
        if os.path.isfile(item_path) and item.lower().endswith(('.mp4', '.ts', '.mkv', '.avi', '.mov')):
            base_name = secure_filename(rel_path.replace(os.sep, '_'))
            contents['videos'].append({
                'name': item,
                'path': rel_path.replace('\\', '/').replace('\'', '\\\''),
                'thumbnail': f"/thumbnails/{base_name}.jpg",
                'preview': f"/previews/{base_name}_preview.mp4"
            })
        elif os.path.isdir(item_path):
            for root, _, files in os.walk(item_path):
                if any(f.lower().endswith(('.mp4', '.ts', '.mkv', '.avi', '.mov')) for f in files):
                    contents['subfolders'].add(item)
                    break

    contents['subfolders'] = sorted(contents['subfolders'])
    contents['videos'] = sorted(contents['videos'], key=lambda x: x['name'])
    return contents

@app.route('/')
def index():
    folder_path = request.args.get('folder', '')
    contents = get_folder_contents(folder_path)
    
    breadcrumbs = []
    if folder_path:
        parts = folder_path.split(os.sep)
        for i in range(len(parts)):
            breadcrumbs.append({
                'name': parts[i],
                'path': os.sep.join(parts[:i+1])
            })
    
    return render_template('index.html', 
                         contents=contents,
                         current_folder=folder_path,
                         breadcrumbs=breadcrumbs)

@app.route('/videos/<path:filename>')
def serve_video(filename):
    return send_from_directory(VIDEO_DIR, filename)

@app.route('/thumbnails/<filename>')
def serve_thumbnail(filename):
    return send_from_directory(THUMBNAIL_DIR, filename)

if __name__ == '__main__':
    # Generate thumbnails at startup
    scan_and_generate_assets()
    
    # start the web server
    host = '0.0.0.0' if not args.host else args.host
    port = 5000 if not args.port else args.port
    if args.prod:
        print("=== Running in pruduction server ===")
        from waitress import serve
        # For production
        serve(app, host=host, port=port, threads=4)
    else:
        print("=== Running in development server ===")
        # For development (optional, you can remove this if you only want production)
        app.run(host=host, port=port, threaded=True, debug=True)