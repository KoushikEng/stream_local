from asyncio import get_running_loop
from sys import platform
from os import path, listdir, sep, walk
from werkzeug.utils import secure_filename
from config import MEDIA_DIR, THUMBNAIL_DIR, PREVIEW_DIR, VIDEO_EXTS, IMAGE_EXTS

# CHANGED: Import from Quart instead of Flask
from quart import Quart, render_template, send_from_directory, request


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
    if platform == 'win32':
        loop = get_running_loop()
        loop.set_exception_handler(handle_win_error_10054)


def get_folder_contents(folder_path):
    abs_path = path.join(MEDIA_DIR, folder_path)
    contents = {'media': [], 'subfolders': set()}

    if not path.exists(abs_path):
        return contents

    for item in listdir(abs_path):
        item_path = path.join(abs_path, item)
        rel_path = path.join(folder_path, item)
        
        if path.isfile(item_path):
            lower_item = item.lower()
            is_video = lower_item.endswith(VIDEO_EXTS)
            is_image = lower_item.endswith(IMAGE_EXTS)
            
            if is_video or is_image:
                base_name = secure_filename(rel_path.replace(sep, '_'))
                media_item = {
                    'name': item,
                    'path': rel_path.replace('\\', '/').replace('\'', '\\\''),
                    'thumbnail': f"/thumbnails/{base_name}.jpg",
                    'type': 'video' if is_video else 'image'
                }
                if is_video:
                    media_item['preview'] = f"/previews/preview_{item}"
                contents['media'].append(media_item)
                
        elif path.isdir(item_path):
            # Recursive check: does this folder contain ANY valid media deep down?
            has_media = False
            for root, _, files in walk(item_path):
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
        parts = folder_path.split(sep)
        for i in range(len(parts)):
            breadcrumbs.append({
                'name': parts[i],
                'path': sep.join(parts[:i+1])
            })
    
    # Quart requires await on render_template
    return await render_template('index.html',
                           path=path,
                           contents=contents,
                           current_folder=folder_path,
                           breadcrumbs=breadcrumbs)

@app.route('/media/<path:filename>')
async def serve_media(filename):
    # send_from_directory is async in Quart - this is the KEY fix for blocking
    return await send_from_directory(MEDIA_DIR, filename)

@app.route('/previews/<path:filename>')
async def serve_preview(filename):
    return await send_from_directory(PREVIEW_DIR, filename)

@app.route('/thumbnails/<filename>')
async def serve_thumbnail(filename):
    return await send_from_directory(THUMBNAIL_DIR, filename)

@app.post('/test')
async def test_route(): # A simple test route to receive data
    data = await request.get_json()
    print("Received data:", data)
    return {'status': 'success', 'received': data}
