import csv
import json
import sqlite3
import urllib.parse as urlparse
from collections import defaultdict
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path
from tqdm.auto import tqdm

import yt_dlp

input_file = "Joe - Streams.tsv"
youtube_datafile = Path("youtube_data.json")


priority = {
    "UCWSt3t0KBgFFIne69grCjPw": 1,  # archivist
    "UC8Ru3ISus2XZig4kE2F7ukA": 2,  # Falco
    "UCSJiNadkPITAaf4y-2uZfQA": 3,  # Bike Chan
    "UCyw8OMf76S-TjMmZSfFqwOg": 4,  # Cat Catasmic
    "UCIJlrEQoJE3eI168TWSl39g": 5,  # Joseph Anderson Channel Two
    "UCdD5BL-tEQam_M9RSmuzAcg": 6,  #  Mike322
    "UCPLra5AnTQFYNvxt7bgo9hA": 7,  # Weed Lol
}


def get_video(info):
    date, vod_id = info
    yt_ops = {
        "skip_download": True,
        "quiet": True,
    }
    url = f"https://www.youtube.com/watch?v={vod_id}"
    with yt_dlp.YoutubeDL(yt_ops) as ydl:
        data = ydl.extract_info(url, download=False)

    entry = {
        "video_id": vod_id,
        "vod_date": date,
        "title": data["title"],
        "description": data["description"],
        "upload_date": data["upload_date"],
        "duration": data["duration"],
        "channel": data["channel_id"] if "channel_id" in data else "",
    }
    return entry


def video_id_from_url(value):
    """
    Examples:
    - http://youtu.be/SA2iWivDJiE
    - http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu
    - http://www.youtube.com/embed/SA2iWivDJiE
    - http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US
    """
    query = urlparse.urlparse(value)
    if query.hostname == "youtu.be":
        return query.path[1:]
    if query.hostname in ("www.youtube.com", "youtube.com"):
        if query.path == "/watch":
            p = urlparse.parse_qs(query.query)
            return p["v"][0]
        if query.path[:7] == "/embed/":
            return query.path.split("/")[2]
        if query.path[:3] == "/v/":
            return query.path.split("/")[2]
    # fail?
    return None


def create_db():
    connection = sqlite3.connect("./data_yt.db")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    # Create a table if it doesn't exist
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            vod_date TEXT,
            title TEXT,
            description TEXT,
            upload_date TEXT,
            channel TEXT,
            duration INTEGER
        )
    """
    )

    return connection, cursor


def get_youtube_urls():
    with open(input_file, "r", newline="") as in_file:
        tsv_reader = csv.reader(in_file, delimiter="\t")
        youtube_urls = []
        for row in tsv_reader:
            if not row[0]:
                continue

            date_str = row[1]
            try:
                # convert the date to the "yyyymmdd" format
                date_obj = datetime.strptime(date_str, "%a, %m/%d/%Y")
                formatted_date = date_obj.strftime("%Y%m%d")
            except ValueError:
                print(f"Invalid date format in row: {row}")

            for field in row:
                video_id = video_id_from_url(field)
                if video_id is not None:
                    youtube_urls.append((formatted_date, video_id))
    return youtube_urls


def insert_missing(connection, cursor, youtube_urls):
    cursor.execute("SELECT video_id FROM videos")
    db_videos = set(row["video_id"] for row in cursor.fetchall())
    todo_urls = [url for url in youtube_urls if url[1] not in db_videos]
    if not todo_urls:
        return

    with Pool(8) as pool:
        for entry in tqdm(pool.imap_unordered(get_video, todo_urls), total=len(todo_urls)):
            cursor.execute(
                "INSERT OR IGNORE INTO videos (video_id, vod_date, title, description, upload_date, channel, duration) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    entry["video_id"],
                    entry["vod_date"],
                    entry["title"],
                    entry["description"],
                    entry["upload_date"],
                    entry["channel"],
                    entry["duration"],
                ),
            )
            connection.commit()


def get_yt_by_date(connection, cursor):
    cursor.execute("SELECT * FROM videos")
    yt_by_date = defaultdict(list)
    for row in cursor:
        entry = {
            "video_id": row["video_id"],
            "duration": row["duration"],
            "priority": priority.get(row["channel"], 999),
        }
        yt_by_date[row["vod_date"]].append(entry)

    for date in yt_by_date:
        yt_by_date[date].sort(key=lambda x: x["priority"])
    return yt_by_date


if __name__ == "__main__":
    youtube_urls = get_youtube_urls()
    connection, cursor = create_db()
    insert_missing(connection, cursor, youtube_urls)
    yt_by_date = get_yt_by_date(connection, cursor)

    with open(youtube_datafile, "w") as f:
        json.dump(yt_by_date, f, indent=4, sort_keys=True, default=str)
