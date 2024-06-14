import argparse
import datetime
import logging
import os
import subprocess

def merge_video(input_dir, output_dir, framerate=30):
    def get_filepath(now, input_dir, output_dir):
        year = str(now.year)
        month = str(now.month)
        day = str(now.day)
        video_filename = f"{now.strftime('%Y-%m-%d')}.mp4"
        video_filepath = os.path.join(output_dir, year, month, day, video_filename)
        snapshots_dir = os.path.join(input_dir, year, month, day)
        return video_filepath, snapshots_dir
    
    now = datetime.datetime.now()
    logging.info(f"Merging video for {now.strftime('%Y-%m-%d %H:%M:%S')}")
    video_filepath, snapshots_dir = get_filepath(now, input_dir, output_dir)
    os.makedirs(os.path.dirname(video_filepath), exist_ok=True)
    
    # create ffmpeg input.txt
    jpg_files = sorted([f for f in os.listdir(snapshots_dir) if f.endswith('.jpg')])
    with open(os.path.join(snapshots_dir, "input.txt"), "w") as f:
        for file in jpg_files:
            f.write(f"file '{os.path.join(snapshots_dir, file)}'\n")

    # merge
    cmd = f"ffmpeg -f concat -safe 0 -i '{os.path.join(snapshots_dir, 'input.txt')}' -framerate {framerate} -c:v libx264 -pix_fmt yuv420p '{video_filepath}' -y"
    subprocess.run(cmd, shell=True, capture_output=True)
    
    # make latest link
    yesterday = now - datetime.timedelta(days=1)
    yesterday_video_filepath, _ = get_filepath(yesterday, input_dir, output_dir)
    
    def make_link(src, dst):
        if os.path.exists(dst):
            os.remove(dst)
        os.symlink(src, dst)
    make_link(video_filepath, os.path.join(output_dir, 'today.mp4'))
    make_link(yesterday_video_filepath, os.path.join(output_dir, 'yesterday.mp4'))
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-i', '--snapshot-top-dir', help='Directory save the snapshot')
    parser.add_argument('-o', '--video-top-dir', help='Directory to save the mereged video')
    args = parser.parse_args()
    merge_video(args.snapshot_top_dir, args.video_top_dir)
    