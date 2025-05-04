import os
from flask import Flask, render_template, send_from_directory, request, Response
import argparse
import ffmpeg
from werkzeug.utils import secure_filename
import random

parser = argparse.ArgumentParser()
parser.add_argument('dir', nargs='?', type=str)
parser.add_argument('-host', '-u', help="host")
parser.add_argument('-port', '-p', type=int, help="port")
parser.add_argument('--prod', action='store_true')
args = parser.parse_args()

app = Flask(__name__)

# Configure the video directory
VIDEO_DIR = "C:\\Users\\koushik\\Downloads" if not args.dir else args.dir
THUMBNAIL_DIR = os.path.join(os.path.dirname(__file__), "thumbnails")  # Where to store thumbnails

# Ensure thumbnail directory exists
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

def get_video_duration(video_path):
    try:
        probe = ffmpeg.probe(video_path)
        return float(probe['format']['duration'])
    except:
        return 10  # Default duration if probing fails

def generate_thumbnail(video_path, thumbnail_path):
    try:
        duration = get_video_duration(video_path)
        random_time = random.uniform(1, max(2, duration-1))  # Between 1s and (duration-1)s
        
        (
            ffmpeg.input(video_path, ss=str(random_time))
            .output(thumbnail_path, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True, quiet=True)
        )
        return True
    except ffmpeg.Error as e:
        print(f"Error generating thumbnail for {video_path}: {e.stderr.decode()}")
        return False
    except Exception as e:
        print(f"Unexpected error with {video_path}: {str(e)}")
        return False

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
            # Generate thumbnail path
            thumb_name = secure_filename(f"{item}.jpg")
            thumb_path = os.path.join(THUMBNAIL_DIR, thumb_name)
            
            # Generate thumbnail if it doesn't exist or is older than the video
            if not os.path.exists(thumb_path) or (
                os.path.getmtime(item_path) > os.path.getmtime(thumb_path)):
                generate_thumbnail(item_path, thumb_path)
            
            contents['videos'].append({
                'name': item,
                'path': rel_path.replace('\\', '\\\\'),
                'thumbnail': f"/thumbnails/{thumb_name}"
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
    app.run(host='0.0.0.0', port=5000, threaded=True)