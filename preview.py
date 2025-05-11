import os
import random
import shutil
import ffmpeg
import argparse
from concurrent.futures import ProcessPoolExecutor
import time
import logging
from collections import namedtuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_previewer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Define a clip data structure
ClipInfo = namedtuple('ClipInfo', ['start_time', 'file_path'])

def get_video_duration(input_video):
    """Get the duration of the video in seconds with proper error handling."""
    try:
        probe = ffmpeg.probe(input_video)
        duration = float(probe['format']['duration'])
        logger.debug(f"Duration of {input_video}: {duration} seconds")
        return duration
    except ffmpeg.Error as e:
        logger.error(f"FFprobe error for {input_video}: {e.stderr.decode().strip()}")
    except Exception as e:
        logger.error(f"Error probing {input_video}: {str(e)}")
    return 0

def extract_random_clips(input_video, num_clips, clip_duration, temp_dir):
    """Extract multiple random clips from the video, ensuring no overlaps."""
    total_duration = get_video_duration(input_video)
    clips = []
    
    if total_duration <= clip_duration:
        # For very short videos, just use the entire video
        clip_path = os.path.join(temp_dir, "clip_0.mp4")
        if extract_single_clip(input_video, clip_path, 0, total_duration):
            clips.append(ClipInfo(0, clip_path))
        return clips
    
    # Calculate possible start times
    max_start = total_duration - clip_duration
    if num_clips * clip_duration > max_start:
        # Adjust clip duration if there's not enough space
        clip_duration = max_start / num_clips
        logger.info(f"Adjusting clip duration to {clip_duration:.2f}s to fit all clips")
    
    # Generate random non-overlapping start times
    start_times = set()
    while len(start_times) < num_clips:
        start_time = random.uniform(0, max_start)
        # Ensure no overlaps with existing clips
        if not any(abs(start_time - st) < clip_duration for st in start_times):
            start_times.add(start_time)
    
    # Extract the clips
    for i, start_time in enumerate(sorted(start_times)):  # Sort by time
        clip_path = os.path.join(temp_dir, f"clip_{i}.mp4")
        if extract_single_clip(input_video, clip_path, start_time, clip_duration):
            clips.append(ClipInfo(start_time, clip_path))
    
    return clips

def extract_single_clip(input_video, output_clip, start_time, duration):
    """Extract a specific clip segment with validation."""
    try:
        logger.debug(f"Extracting clip: {start_time:.2f}s for {duration:.2f}s from {input_video}")
        
        (
            ffmpeg.input(input_video, ss=start_time)
            .output(output_clip, t=duration, c='copy')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        # Verify the output
        if os.path.exists(output_clip) and os.path.getsize(output_clip) > 0:
            return True
        logger.error(f"Failed to create valid clip: {output_clip}")
    except ffmpeg.Error as e:
        logger.error(f"Clip extraction error: {e.stderr.decode().strip()}")
    except Exception as e:
        logger.error(f"Unexpected extraction error: {str(e)}")
    return False

def create_transition(input1, input2, transition_duration, output_file):
    """Create transition between clips with validation."""
    try:
        if not (os.path.exists(input1) and os.path.exists(input2)):
            logger.error(f"Missing input files for transition: {input1} or {input2}")
            return False
            
        logger.debug(f"Creating transition between {input1} and {input2}")
        
        (
            ffmpeg.filter([ffmpeg.input(input1), ffmpeg.input(input2)], 'xfade', 
                         transition='fade', duration=transition_duration, offset=0)
            .output(output_file, preset='ultrafast', movflags='faststart')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        return os.path.exists(output_file) and os.path.getsize(output_file) > 1024
    except ffmpeg.Error as e:
        logger.error(f"Transition error: {e.stderr.decode().strip()}")
    return False

def create_video_preview(input_video, output_preview, num_clips=4, clip_duration=5, transition_duration=1.0):
    """Create preview with time-sorted clips and transitions."""
    logger.info(f"Creating preview for {input_video}")
    
    if not os.path.exists(input_video):
        logger.error(f"Input file not found: {input_video}")
        return False
    
    # Create unique temp directory
    temp_dir = f"preview_temp_{os.path.basename(input_video)}_{int(time.time())}"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Step 1: Extract random non-overlapping clips sorted by time
        clips = extract_random_clips(input_video, num_clips, clip_duration, temp_dir)
        if not clips:
            logger.error("No valid clips extracted")
            return False
        
        # Step 2: Create transitions between time-sorted clips
        transition_files = []
        for i in range(len(clips) - 1):
            transition_path = os.path.join(temp_dir, f"transition_{i}.mp4")
            if create_transition(
                clips[i].file_path, 
                clips[i+1].file_path, 
                transition_duration,
                transition_path
            ):
                transition_files.append(transition_path)
            else:
                logger.warning(f"Failed to create transition {i}")
        
        # Step 3: Build final video with time-sorted clips
        try:
            inputs = []
            for i, clip in enumerate(clips):
                inputs.append(ffmpeg.input(clip.file_path))
                if i < len(transition_files):
                    inputs.append(ffmpeg.input(transition_files[i]))
            
            # Use optimized encoding settings
            (
                ffmpeg.concat(*inputs, v=1, a=0)
                .output(output_preview, vcodec='libx264', crf=23, preset='veryfast')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            # Verify final output
            if os.path.exists(output_preview) and os.path.getsize(output_preview) > 1024:
                logger.info(f"Successfully created preview: {output_preview}")
                return True
            logger.error(f"Invalid output file: {output_preview}")
        except ffmpeg.Error as e:
            logger.error(f"Concatenation error: {e.stderr.decode().strip()}")
    finally:
        # Cleanup
        # for clip in clips:
        #     try:
        #         os.remove(clip.file_path)
        #     except:
        #         pass
        # for tf in transition_files:
        #     try:
        #         os.remove(tf)
        #     except:
        #         pass
        try:
            shutil.rmtree(temp_dir)
            os.rmdir(temp_dir)
        except Exception as e:
            logger.exception(e)
    
    return False

def process_video_file(args):
    """Process a single video file with the given arguments."""
    input_video, output_dir, num_clips, clip_duration, transition_duration = args
    
    if not os.path.exists(input_video):
        logger.error(f"Input video not found: {input_video}")
        return False
    
    output_name = f"preview_{os.path.basename(input_video)}"
    output_preview = os.path.join(output_dir, output_name)
    
    # Skip if output already exists
    if os.path.exists(output_preview):
        logger.info(f"Skipping existing preview: {output_preview}")
        return True
    
    return create_video_preview(
        input_video,
        output_preview,
        num_clips,
        clip_duration,
        transition_duration
    )

def batch_create_previews(input_dir, output_dir, num_clips=4, clip_duration=5, transition_duration=1.0, max_workers=4):
    """Batch process all videos in a directory."""
    if not os.path.exists(input_dir):
        logger.error(f"Input directory not found: {input_dir}")
        return False
    
    os.makedirs(output_dir, exist_ok=True)
    
    video_files = []
    for root, _, files in os.walk(input_dir):
        if "$RECYCLE.BIN" in root or "previews" in root:
            continue
        for f in files:
            if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.flv', '.webm')):
                video_files.append(os.path.join(root, f))
    
    if not video_files:
        logger.error(f"No video files found in {input_dir}")
        return False
    
    logger.info(f"Processing {len(video_files)} videos with {max_workers} workers...")
    
    args_list = [
        (video, output_dir, num_clips, clip_duration, transition_duration)
        for video in video_files
    ]
    
    success_count = 0
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(process_video_file, args_list)
        success_count = sum(results)
    
    logger.info(f"Completed: {success_count} successful, {len(video_files)-success_count} failed")
    return success_count > 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create video previews with time-sorted clips.')
    parser.add_argument('input', help='Input video file or directory')
    parser.add_argument('output', help='Output file or directory')
    parser.add_argument('--num_clips', type=int, default=4, help='Number of clips (default: 4)')
    parser.add_argument('--clip_duration', type=int, default=5, help='Clip duration in seconds (default: 5)')
    parser.add_argument('--transition_duration', type=float, default=1.0, help='Transition duration (default: 1.0)')
    parser.add_argument('--workers', type=int, default=6, help='Parallel workers (default: 4)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    if os.path.isdir(args.input):
        batch_create_previews(
            args.input,
            args.output,
            args.num_clips,
            args.clip_duration,
            args.transition_duration,
            args.workers
        )
    else:
        create_video_preview(
            args.input,
            args.output,
            args.num_clips,
            args.clip_duration,
            args.transition_duration
        )