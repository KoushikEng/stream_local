import os
from flask import Flask, render_template, send_from_directory, request, Response
import argparse
    
parser = argparse.ArgumentParser()
parser.add_argument('dir', nargs='?', type=str)
parser.add_argument('-host', '-u', help="host")
parser.add_argument('-port', '-p', type=int, help="port")
parser.add_argument('--prod', action='store_true')
args = parser.parse_args()

app = Flask(__name__)

# Configure the video directory
VIDEO_DIR = "C:\\Users\\koushik\\Downloads" if not args.dir else args.dir

def get_folder_contents(folder_path):
    """Returns videos and subfolders that contain videos for the given path"""
    abs_path = os.path.join(VIDEO_DIR, folder_path)
    
    contents = {
        'videos': [],
        'subfolders': set()
    }

    # First pass to get immediate contents
    for item in os.listdir(abs_path):
        item_path = os.path.join(abs_path, item)
        rel_path = os.path.join(folder_path, item)
        
        if os.path.isfile(item_path) and item.lower().endswith(('.mp4', '.ts', '.mkv', '.avi', '.mov', '.webm')):
            contents['videos'].append({
                'name': item,
                'path': rel_path.replace('\\', '\\\\'),
                'type': 'video/mp4' if item.lower().endswith('.mp4') else 'video/mp2t' if item.lower().endswith('.ts') else 'video/webm'
            })
        elif os.path.isdir(item_path):
            # Check if the subfolder contains any video files
            for root, _, files in os.walk(item_path):
                if any(f.lower().endswith(('.mp4', '.ts', '.mkv', '.avi', '.mov', '.webm')) for f in files):
                    contents['subfolders'].add(item)
                    break

    # Convert set to sorted list
    contents['subfolders'] = sorted(contents['subfolders'])
    # Sort videos
    contents['videos'] = sorted(contents['videos'], key=lambda x: x['name'])
    
    return contents

@app.route('/')
def index():
    folder_path = request.args.get('folder', '')
    contents = get_folder_contents(folder_path)
    
    # Calculate breadcrumbs
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
    video_path = os.path.join(VIDEO_DIR, filename)
    
    # Implement proper streaming for TS files
    if filename.lower().endswith('.ts'):
        def generate():
            with open(video_path, 'rb') as f:
                while True:
                    data = f.read(1024 * 1024)  # 1MB chunks
                    if not data:
                        break
                    yield data
        return Response(generate(), mimetype='video/mp2t')
    
    return send_from_directory(VIDEO_DIR, filename)

if __name__ == '__main__':
    host = '0.0.0.0' if not args.host else args.host
    port = 5000 if not args.port else args.port
    if args.prod:
        print("=== Running in pruduction server ===")
        from waitress import serve
        # For production
        serve(app, host=host, port=port, threads=2)
    else:
        print("=== Running in development server ===")
        # For development (optional, you can remove this if you only want production)
        app.run(host=host, port=port, threaded=True)