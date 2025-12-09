import ffmpeg
import random
import time
from os import path, makedirs, walk, sep
from concurrent.futures import ThreadPoolExecutor
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps  # Added Pillow for image handling
from config import VIDEO_EXTS, IMAGE_EXTS

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
    if not path.exists(thumb_path) or (path.getmtime(file_path) > path.getmtime(thumb_path)):
        if is_video:
            return generate_video_thumbnail(file_path, thumb_path)
        else:
            return generate_image_thumbnail(file_path, thumb_path)
    return True

def scan_and_generate_thumbnails(input_dir, output_dir):
    """
    This remains synchronous because we run it at startup.
    """
    if not path.exists(input_dir):
        logger.error(f"Thumbnail_processor - Input directory not found: {input_dir}")
        return False
    
    makedirs(output_dir, exist_ok=True)
    
    print("Starting media scan and thumbnail generation...")
    start_time = time.time()
    media_files = []
    
    for root, _, files in walk(input_dir):
        if "$RECYCLE.BIN" in root: continue
        for file in files:
            lower_file = file.lower()
            is_video = lower_file.endswith(VIDEO_EXTS)
            is_image = lower_file.endswith(IMAGE_EXTS)
            
            if is_video or is_image:
                file_path = path.join(root, file)
                rel_path = path.relpath(file_path, input_dir)
                # Create a safe filename for the thumbnail
                thumb_name = secure_filename(f"{rel_path.replace(sep, '_')}.jpg")
                thumb_path = path.join(output_dir, thumb_name)
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