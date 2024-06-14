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
    video_filename = f"{now.strftime('%Y-%m-%d')}.mkv"
    video_filepath = os.path.join(output_dir, year, month, day, video_filename)
    os.makedirs(os.path.dirname(video_filepath), exist_ok=True)
    snapshots_dir = os.path.join(input_dir, year, month, day)
    
    # rename
    i = 0
    for snapshot in os.listdir(snapshots_dir):
        if not snapshot.endswith('.jpg'):
            continue
        snapshot_path = os.path.join(snapshots_dir, snapshot)
        new_snapshot_path = os.path.join(snapshots_dir, f"{i:05d}.jpg")
        os.rename(snapshot_path, new_snapshot_path)
    
    cmd = f"ffmpeg -framerate {framerate} -i '{snapshots_dir}/%05d.jpg' -c:v libx264 -pix_fmt yuv420p '{video_filepath}'"
    logging.info(f"Running command: {cmd}")
    subprocess.run(cmd, shell=True)
    logging.info(f"Finished")
    
    # make latest link
    latest_video_filepath = os.path.join(output_dir, 'latest.mkv')
    if os.path.exists(latest_video_filepath):
        os.remove(latest_video_filepath)
    os.symlink(video_filepath, latest_video_filepath)
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-i', '--snapshot-top-dir', help='Directory save the snapshot')
    parser.add_argument('-o', '--video-top-dir', help='Directory to save the mereged video')
    args = parser.parse_args()
    merge_video(args.snapshot_top_dir, args.video_top_dir)
    