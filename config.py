from os import path, makedirs

# Configure the video directory
MEDIA_DIR = ""

def set_media_dir(dir_path):
    global MEDIA_DIR
    MEDIA_DIR = dir_path


THUMBNAIL_DIR = path.join(path.dirname(__file__), "thumbnails")
PREVIEW_DIR = path.join(path.dirname(__file__), "previews")

# Ensure directory exists
makedirs(THUMBNAIL_DIR, exist_ok=True)
makedirs(PREVIEW_DIR, exist_ok=True)

VIDEO_EXTS = ('.mp4', '.ts', '.mkv', '.avi', '.mov', '.webm')
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')