import os
import random
import ffmpeg
import argparse
from concurrent.futures import ProcessPoolExecutor
import time
import logging

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

def extract_random_clip(input_video, output_clip, clip_duration=5):
    """Extract a random clip with validation and error handling."""
    try:
        total_duration = get_video_duration(input_video)
        
        if total_duration <= 0:
            logger.error(f"Invalid duration for {input_video}")
            return False
            
        if total_duration <= clip_duration:
            start_time = 0
            clip_duration = total_duration
        else:
            max_start = total_duration - clip_duration
            start_time = random.uniform(0, max_start)
        
        logger.info(f"Extracting clip from {input_video} (start: {start_time:.2f}s, duration: {clip_duration}s)")
        
        (
            ffmpeg.input(input_video, ss=start_time)
            .output(output_clip, t=clip_duration, c='copy')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        # Verify the output file was created
        if os.path.exists(output_clip) and os.path.getsize(output_clip) > 0:
            return True
        else:
            logger.error(f"Failed to create valid clip: {output_clip}")
            return False
            
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error processing {input_video}: {e.stderr.decode().strip()}")
    except Exception as e:
        logger.error(f"Unexpected error with {input_video}: {str(e)}")
    return False

def create_transition(input1, input2, transition_duration=1.0, output_file='transition.mp4'):
    """Create transition with validation checks."""
    try:
        # First verify both input files exist
        if not (os.path.exists(input1) and os.path.exists(input2)):
            logger.error(f"Input files missing for transition: {input1} or {input2}")
            return None
            
        logger.debug(f"Creating transition between {input1} and {input2}")
        
        # Use faster encoding settings for transitions
        (
            ffmpeg.filter([ffmpeg.input(input1), ffmpeg.input(input2)], 'xfade', 
                         transition='fade', duration=transition_duration, offset=0)
            .output(output_file, preset='ultrafast', movflags='faststart')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        # Verify transition file
        if os.path.exists(output_file) and os.path.getsize(output_file) > 1024:  # At least 1KB
            return output_file
        else:
            logger.error(f"Failed to create valid transition file: {output_file}")
            return None
            
    except ffmpeg.Error as e:
        logger.error(f"Transition error: {e.stderr.decode().strip()}")
    except Exception as e:
        logger.error(f"Unexpected transition error: {str(e)}")
    return None

def create_video_preview(input_video, output_preview, num_clips=4, clip_duration=5, transition_duration=1.0):
    """Create preview with comprehensive error handling."""
    logger.info(f"Starting preview creation for {input_video}")
    
    if not os.path.exists(input_video):
        logger.error(f"Input file not found: {input_video}")
        return False
    
    temp_dir = f"temp_preview_{int(time.time())}"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Step 1: Extract random clips
        clip_files = []
        for i in range(num_clips):
            clip_path = os.path.join(temp_dir, f"clip_{os.path.basename(input_video)}_{i}.mp4")
            if extract_random_clip(input_video, clip_path, clip_duration, i, num_clips):
                clip_files.append(clip_path)
            else:
                logger.warning(f"Skipping failed clip {i} for {input_video}")
        
        if not clip_files:
            logger.error(f"No valid clips extracted for {input_video}")
            return False
            
        # Step 2: Create transitions
        transition_files = []
        for i in range(len(clip_files) - 1):
            transition_path = os.path.join(temp_dir, f"transition_{i}.mp4")
            transition = create_transition(
                clip_files[i], 
                clip_files[i+1], 
                transition_duration,
                transition_path
            )
            if transition:
                transition_files.append(transition)
            else:
                logger.warning(f"Skipping transition {i} for {input_video}")
        
        # Step 3: Build final video
        try:
            inputs = []
            for i in range(len(clip_files)):
                inputs.append(ffmpeg.input(clip_files[i]))
                if i < len(transition_files):
                    inputs.append(ffmpeg.input(transition_files[i]))
            
            # Use faster encoding for previews
            (
                ffmpeg.concat(*inputs, v=1, a=0)
                .output(output_preview, 
                       movflags='faststart', 
                       preset='ultrafast', 
                       crf=23, 
                       acodec='aac', 
                       strict='experimental')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            # Final verification
            if os.path.exists(output_preview) and os.path.getsize(output_preview) > 1024:
                logger.info(f"Successfully created preview: {output_preview}")
                return True
            else:
                logger.error(f"Failed to create valid preview file: {output_preview}")
                return False
                
        except ffmpeg.Error as e:
            logger.error(f"Final concatenation error: {e.stderr.decode().strip()}")
            return False
            
    finally:
        # Cleanup temp files
        for f in clip_files + transition_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception as e:
                logger.warning(f"Couldn't delete temp file {f}: {str(e)}")
        try:
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception as e:
            logger.warning(f"Couldn't delete temp dir {temp_dir}: {str(e)}")
    
    return False

def process_video_file(args):
    """Process a single video file with error handling."""
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
    """Batch process videos with proper resource management."""
    if not os.path.exists(input_dir):
        logger.error(f"Input directory not found: {input_dir}")
        return False
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all video files
    video_files = []
    for root, _, files in os.walk(input_dir):
        for f in files:
            if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.flv', '.webm')):
                video_files.append(os.path.join(root, f))
    
    if not video_files:
        logger.error(f"No supported video files found in {input_dir}")
        return False
    
    logger.info(f"Found {len(video_files)} videos to process")
    
    # Prepare arguments for each video
    args_list = [
        (video, output_dir, num_clips, clip_duration, transition_duration)
        for video in video_files
    ]
    
    # Process videos with thread pool
    success_count = 0
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(process_video_file, args_list)
        success_count = sum(results)
    
    logger.info(f"Batch processing completed. Success: {success_count}/{len(video_files)}")
    return success_count > 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create video previews with transitions.')
    parser.add_argument('input', help='Input video file or directory')
    parser.add_argument('output', help='Output file or directory')
    parser.add_argument('--num_clips', type=int, default=4, help='Number of clips (default: 4)')
    parser.add_argument('--clip_duration', type=int, default=5, help='Clip duration in seconds (default: 5)')
    parser.add_argument('--transition_duration', type=float, default=1.0, help='Transition duration (default: 1.0)')
    parser.add_argument('--workers', type=int, default=4, help='Parallel workers (default: 4)')
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