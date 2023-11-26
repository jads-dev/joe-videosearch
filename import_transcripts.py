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

connection = sqlite3.connect("./data.db")
connection.row_factory = sqlite3.Row
cursor = connection.cursor()


# Create a table if it doesn't exist
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS vods (
        vod_id TEXT PRIMARY KEY,
        chat_id TEXT,
        video_url TEXT,
        title TEXT,
        game TEXT,
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


def import_srt_to_sqlite(srt_file, vod_id):
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


def search_ia(dates):
    vod_files = defaultdict(list)
    suffixes = {f"{date[:4]}{date[5:7]}" for date in dates}
    for suffix in tqdm(suffixes):
        identifier = f"josephanderson_twitch_{suffix}"
        item = ia.get_item(identifier)
        video_files = [file for file in item.files if file["format"] in ("MPEG4", "h.264", "h.264 IA")]
        for file in video_files:
            p = Path(file["name"])
            vod_id = p.stem.split(" - ")[-1].replace(".ia", "")
            vod_files[vod_id].append({"identifier": identifier, "name": file["name"], "size": file["size"]})

    return vod_files


games_by_date = defaultdict(list)
with open("streamdates.tsv", "r", newline="") as in_file:
    tsv_reader = csv.reader(in_file, delimiter="\t")
    for row in tsv_reader:
        if len(row) >= 2:
            date, game = row[1], row[2]
            games_by_date[date].append(game)


def get_game_by_date(date):
    games = games_by_date.get(date, [])

    if len(games) == 1:
        return games[0]
    else:
        return None


def fill_vod_metadata():
    cursor.execute("SELECT * FROM vods where video_url is null")
    dates = {row["date"] for row in cursor}
    vod_files = search_ia(dates)

    cursor.execute("SELECT * FROM vods where video_url is null or chat_id is null or game is null")

    twitch_pattern = r"^v\d+$"
    rows = [row for row in cursor.fetchall()]
    for row in tqdm(rows):
        chat_id = row["chat_id"]
        title = None  # file title might be wrong so we force update it if we find a new one
        game = row["game"]
        video_url = row["video_url"]

        if not chat_id and re.match(twitch_pattern, row["vod_id"]):
            chat_id = row["vod_id"]

        chat_filename = chat_id.lstrip("v") if chat_id else "none"
        chat_file = Path(f"D:/Downloads/joe/chat/{chat_filename}.json")
        if chat_file.exists():
            with open(chat_file, "r", encoding="utf-8") as f:
                chat_metadata = json.load(f)["video"]
            if not title:
                title = chat_metadata.get("title", row["title"])  # if we can't find a new title use the db one
            if not game:
                game = chat_metadata.get("game", None)
            if not game:  # fallback method
                game = get_game_by_date(row["date"])

        if not video_url:
            files = vod_files[row["vod_id"]]
            try:
                smallest_file = min(files, key=lambda x: x["size"])
            except:
                # print content of sqlite row
                print("\n\nCan't find video file for vod_id:")
                for key in row.keys():
                    print(f"{key}: {row[key]}")
                print("\n\n")
                continue
            filename_url = urllib.parse.quote(smallest_file["name"])
            video_url = f"https://archive.org/download/{smallest_file['identifier']}/{filename_url}"

        cursor.execute("update vods set chat_id = ?, video_url = ?, title = ?, game = ? where vod_id = ?", (chat_id, video_url, title, game, row["vod_id"]))
        connection.commit()


transcripts_folder = Path(R"D:\Downloads\joe\transcripts")
data_to_import = []
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
        import_srt_to_sqlite(file, vod_id)
        cursor.execute("INSERT INTO vods (vod_id, title, date) VALUES (?,?,?)", (vod_id, title, date))
connection.commit()


fill_vod_metadata()


connection.close()
export_db()
