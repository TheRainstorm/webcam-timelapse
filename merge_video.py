import argparse
import datetime
import logging
import os
import subprocess

def merge_video(input_dir, output_dir, framerate=30):
    now = datetime.datetime.now()
    year = str(now.year)
    month = str(now.month)
    day = str(now.day)
    logging.info(f"Creating video for {now.strftime('%Y-%m-%d')}")
    video_filename = f"{now.strftime('%Y-%m-%d')}.mp4"
    video_filepath = os.path.join(output_dir, year, month, day, video_filename)
    os.makedirs(os.path.dirname(video_filepath), exist_ok=True)
    snapshots_dir = os.path.join(input_dir, year, month, day)
    
    jpg_files = sorted([f for f in os.listdir(snapshots_dir) if f.endswith('.jpg')])

    with open(os.path.join(snapshots_dir, "input.txt"), "w") as f:
        for file in jpg_files:
            f.write(f"file '{os.path.join(snapshots_dir, file)}'\n")

    cmd = f"ffmpeg -f concat -safe 0 -i '{os.path.join(snapshots_dir, 'input.txt')}' -framerate {framerate} -c:v libx264 -pix_fmt yuv420p '{video_filepath}' -y"
    logging.info(f"Running command: {cmd}")
    subprocess.run(cmd, shell=True, capture_output=True)
    logging.info(f"Finished")
    
    # make latest link
    latest_video_filepath = os.path.join(output_dir, 'latest.mp4')
    if os.path.exists(latest_video_filepath):
        os.remove(latest_video_filepath)
    os.symlink(video_filepath, latest_video_filepath)
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-i', '--snapshot-top-dir', help='Directory save the snapshot')
    parser.add_argument('-o', '--video-top-dir', help='Directory to save the mereged video')
    args = parser.parse_args()
    merge_video(args.snapshot_top_dir, args.video_top_dir)
    