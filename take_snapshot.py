import argparse
import datetime
import logging
import os
import requests

def download_snapshot(snapshot_url, output_dir):
    now = datetime.datetime.now()
    year = str(now.year)
    month = str(now.month)
    day = str(now.day)
    filename = f"{now.strftime('%Y-%m-%d-%H-%M-%S')}.jpg"
    filepath = os.path.join(output_dir, year, month, day, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    r = requests.get(snapshot_url)
    if r.status_code == 200:
        with open(filepath, 'wb') as f:
            f.write(r.content)
    else:
        logging.warning(f"Failed to download snapshot at {filename}")
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Take a snapshot of the current state of the system')
    parser.add_argument('-u', '--snapshot-url', help='URL to take the snapshot from')
    parser.add_argument('-o', '--output-dir', help='Directory to save the snapshot')
    args = parser.parse_args()
    download_snapshot(args.snapshot_url, args.output_dir)
    