import csv
import datetime
import glob
import json
import os
import re
import shutil
import sqlite3
import urllib.parse
from collections import defaultdict
from pathlib import Path

import internetarchive as ia
import pysrt
from tqdm.auto import tqdm


def create_db():
    connection = sqlite3.connect("./data.db")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    # Create a table if it doesn't exist
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vods (
            vod_id TEXT PRIMARY KEY,
            video_url_peertube TEXT,
            title TEXT,
            date TEXT
        )
    """
    )

    cursor.execute(
        """
            CREATE TABLE IF NOT EXISTS transcripts (
                vod TEXT,
                sub_index INTEGER,
                speaker INTEGER,
                start_time TEXT,
                end_time TEXT,
                content TEXT
            )
        """
    )
    return connection, cursor


def import_srt_to_sqlite(connection, cursor, srt_file, vod_id):
    subtitles = pysrt.open(srt_file)

    pattern = r"\[\w+_(\d+)\]: (.+)"
    records = []

    for index, subtitle in enumerate(subtitles):
        match = re.match(pattern, subtitle.text)
        if match:
            speaker_id = match.group(1)
            content = match.group(2)
        else:
            speaker_id = 99
            content = subtitle.text

        record = (
            vod_id,
            index + 1,
            speaker_id,
            str(subtitle.start),
            str(subtitle.end),
            content,
        )
        records.append(record)

    cursor.executemany(
        """
        INSERT INTO transcripts (vod, sub_index, speaker, start_time, end_time, content)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        records,
    )

    connection.commit()


def split_db(file, dir):
    size = os.path.getsize(file)
    server_chunk_size = 10 * 1024 * 1024
    suffix_length = 3

    map(os.remove, glob.glob(f"{dir}/db.sqlite3*"))
    split_command = f'split "{file}" --bytes={server_chunk_size} "{dir}/db.sqlite3." --suffix-length={suffix_length} --numeric-suffixes'
    os.system(split_command)

    request_chunk_size = os.popen(f'sqlite3 "{file}" "pragma page_size"').read()

    config = {
        "serverMode": "chunked",
        "requestChunkSize": request_chunk_size.strip(),
        "databaseLengthBytes": size,
        "serverChunkSize": server_chunk_size,
        "urlPrefix": "db.sqlite3.",
        "suffixLength": suffix_length,
    }

    with open(f"{dir}/config.json", "w") as f:
        json.dump(config, f)


def cleanup():
    dir_path = Path("./static")
    prefix = "data"

    for item in dir_path.iterdir():
        if item.name.startswith(prefix):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)


def export_db():
    cleanup()
    now = datetime.datetime.now()
    dir_name = f"data-{now.year}{now.month:02}{now.day:02}"
    os.makedirs(f"./static/{dir_name}", exist_ok=True)
    split_db("data.db", f"static/{dir_name}/")
    with open("static/data.json", "w") as f:
        data = {"dir_name": f"./{dir_name}"}
        json.dump(data, f)


def fill_vod_metadata(connection, cursor):

    cursor.execute("SELECT external_id, name as title, url as video_url_peertube, original_publish_date as date FROM peertube_videos")
    videos_peertube = {row["external_id"]: row for row in cursor.fetchall()}

    cursor.execute("SELECT * FROM vods where video_url_peertube is null")

    twitch_pattern = r"^v\d+$"
    rows = [row for row in cursor.fetchall()]
    for row in tqdm(rows):
        vod_id = row["vod_id"]
        date = row["date"]
        title = None  # file title might be wrong so we force update it if we find a new one
        video_url_peertube = row["video_url_peertube"]

        is_twitch = re.match(twitch_pattern, vod_id)

        external_id = "twitch:" + vod_id if is_twitch else "youtube:" + vod_id
        if external_id not in videos_peertube:
            print(f"Video {external_id} not found in peertube database")
            continue

        if not video_url_peertube:
            video_url_peertube = videos_peertube[external_id]["video_url_peertube"]
        if not title:
            title = videos_peertube[external_id]["title"]
        if not date:
            date = videos_peertube[external_id]["date"]
            date = date[:10] if date else None

        cursor.execute(
            "update vods set video_url_peertube = ?,  title = ?, date = ? where vod_id = ?",
            (video_url_peertube, title, date, vod_id),
        )
        connection.commit()


if __name__ == "__main__":
    connection, cursor = create_db()
    transcripts_folder = Path(R"D:\Downloads\joe\transcripts")
    data_to_import = []

    done_work = False
    for file in tqdm(list(transcripts_folder.glob("*.srt"))):
        splits = file.stem.split(" - ")
        vod_id = splits[-1]
        title = " - ".join(splits[1:-1])

        date = splits[0]
        date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"

        cursor.execute("SELECT vod_id FROM vods WHERE vod_id = ?", (vod_id,))
        existing_record = cursor.fetchone()

        if existing_record:
            continue
            # print(f"File {vod_id} already exists in the database. Skipping...")
        else:
            import_srt_to_sqlite(connection, cursor, file, vod_id)
            cursor.execute("INSERT INTO vods (vod_id, title, date) VALUES (?,?,?)", (vod_id, title, date))
            done_work = True
    connection.commit()

    fill_vod_metadata(connection, cursor)
    connection.close()

    if done_work:
        export_db()
        os.system("update_ghpages.bat")
