import requests
import json
import sqlite3
import re
from tqdm.auto import tqdm
from dotenv import load_dotenv
import os


def get_client_credentials(instance_url):
    client_url = f"{instance_url}/api/v1/oauth-clients/local"
    response = requests.get(client_url)
    response.raise_for_status()
    data = response.json()
    return data["client_id"], data["client_secret"]


def get_user_token(instance_url, client_id, client_secret, username, password):
    token_url = f"{instance_url}/api/v1/users/token"
    data = {"client_id": client_id, "client_secret": client_secret, "grant_type": "password", "response_type": "code", "username": username, "password": password}
    response = requests.post(token_url, data=data)
    response.raise_for_status()
    return response.json()["access_token"]


def get_peertube_videos(instance_url, access_token, start=0, count=30):
    headers = {"Authorization": f"Bearer {access_token}"}
    api_url = f"{instance_url}/api/v1/videos"
    params = {"start": start, "count": count, "sort": "-createdAt", "include": 1}
    response = requests.get(api_url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data["data"]


def get_video_source(instance_url, video_id, access_token):
    api_url = f"{instance_url}/api/v1/videos/{video_id}/source"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("filename", None)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None
        else:
            raise


def get_user_imports(instance_url, access_token):
    api_url = f"{instance_url}/api/v1/users/me/videos/imports"
    headers = {"Authorization": f"Bearer {access_token}"}
    all_imports = []
    start = 0
    count = 30

    while True:
        params = {"start": start, "count": count}
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        imports = data["data"]

        if not imports:
            break

        all_imports.extend(imports)
        start += count

        if len(imports) < count:
            break

    return all_imports


def get_all_videos(instance_url, access_token, conn):
    cursor = conn.cursor()
    all_videos = []
    start = 0
    count = 30

    while True:
        videos = get_peertube_videos(instance_url, access_token, start=start, count=count)
        if not videos:
            break
        for video in videos:
            cursor.execute("SELECT original_filename, external_id FROM peertube_videos WHERE id = ?", (video["id"],))
            result = cursor.fetchone()
            if result is None or (result[0] is None and not result[1]):
                video["original_filename"] = get_video_source(instance_url, video["id"], access_token)
            else:
                video["original_filename"] = result[0]
        all_videos.extend(videos)
        start += count

    imports = get_user_imports(instance_url, access_token)
    for import_data in imports:
        matching_video = next((v for v in all_videos if v["id"] == import_data["video"]["id"]), None)
        if matching_video:
            matching_video["source_url"] = import_data.get("targetUrl")

    return all_videos


def create_database():
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS peertube_videos (
        id TEXT PRIMARY KEY,
        name TEXT,
        description TEXT,
        duration INTEGER,
        views INTEGER,
        likes INTEGER,
        dislikes INTEGER,
        nsfw BOOLEAN,
        thumbnailPath TEXT,
        createdAt TEXT,
        publishedAt TEXT,
        updatedAt TEXT,
        channel TEXT,
        channelId INTEGER,
        privacy TEXT,
        url TEXT,
        original_filename TEXT,
        source_url TEXT,
        manual_id TEXT,
        external_id TEXT,
        original_publish_date TEXT
    )
    """
    )

    conn.commit()
    return conn


def determine_external_id(video):
    if video.get("manual_id"):
        return video["manual_id"]

    if video.get("source_url"):
        twitch_match = re.search(r"v(\d+)(?:\.mp4)?$", video["source_url"])
        if twitch_match:
            return f"twitch:v{twitch_match.group(1)}"
        youtube_match = re.search(r"(?:youtu\.be/|youtube\.com/(?:embed/|v/|watch\?v=|watch\?.+&v=))([^&?/]+)", video["source_url"])
        if youtube_match:
            return f"youtube:{youtube_match.group(1)}"

    if video.get("original_filename"):
        twitch_match = re.search(r"v(\d+)\.mp4$", video["original_filename"])
        if twitch_match:
            return f"twitch:v{twitch_match.group(1)}"
        youtube_match = re.search(r" ([A-Za-z0-9_-]{11})$", video["original_filename"].rsplit(".", 1)[0])
        if youtube_match:
            return f"youtube:{youtube_match.group(1)}"

    return None


def insert_or_update_video(conn, video):
    cursor = conn.cursor()

    # Check if the video already exists
    cursor.execute("SELECT manual_id FROM peertube_videos WHERE id = ?", (video["id"],))
    existing = cursor.fetchone()

    if existing:
        manual_id = existing[0]
        external_id = determine_external_id({**video, "manual_id": manual_id})
        cursor.execute(
            """
        UPDATE peertube_videos SET
            name = ?, description = ?, duration = ?, views = ?, likes = ?,
            dislikes = ?, nsfw = ?, thumbnailPath = ?, createdAt = ?,
            publishedAt = ?, updatedAt = ?, channel = ?, channelId = ?,
            privacy = ?, url = ?, original_filename = ?, source_url = ?,
            external_id = ?, original_publish_date = ?
        WHERE id = ?
        """,
            (
                video["name"],
                video["description"],
                video["duration"],
                video["views"],
                video["likes"],
                video["dislikes"],
                video["nsfw"],
                video["thumbnailPath"],
                video["createdAt"],
                video["publishedAt"],
                video["updatedAt"],
                video["channel"]["name"],
                video["channel"]["id"],
                video["privacy"]["id"],
                video["url"],
                video.get("original_filename"),
                video.get("source_url"),
                external_id,
                video.get("originallyPublishedAt"),
                video["id"],
            ),
        )
    else:
        external_id = determine_external_id(video)
        cursor.execute(
            """
        INSERT INTO peertube_videos (
            id, name, description, duration, views, likes, dislikes, nsfw,
            thumbnailPath, createdAt, publishedAt, updatedAt, channel, channelId,
            privacy, url, original_filename, source_url, external_id, original_publish_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                video["id"],
                video["name"],
                video["description"],
                video["duration"],
                video["views"],
                video["likes"],
                video["dislikes"],
                video["nsfw"],
                video["thumbnailPath"],
                video["createdAt"],
                video["publishedAt"],
                video["updatedAt"],
                video["channel"]["name"],
                video["channel"]["id"],
                video["privacy"]["id"],
                video["url"],
                video.get("original_filename"),
                video.get("source_url"),
                external_id,
                video.get("originallyPublishedAt"),
            ),
        )

    conn.commit()


def get_video_info_from_peertube(instance_url, access_token, video_id):
    headers = {"Authorization": f"Bearer {access_token}"}
    api_url = f"{instance_url}/api/v1/videos/{video_id}"
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None


def update_video_date_on_peertube(instance_url, access_token, video_id, new_date):
    headers = {"Authorization": f"Bearer {access_token}"}
    api_url = f"{instance_url}/api/v1/videos/{video_id}"
    data = {"originallyPublishedAt": new_date}
    response = requests.put(api_url, headers=headers, json=data)
    return response.status_code == 204


def update_dates_on_peertube(conn, instance_url, access_token):
    cursor = conn.cursor()

    # get videos without original publish date
    cursor.execute("SELECT id, original_filename FROM peertube_videos WHERE original_publish_date IS NULL")
    videos = cursor.fetchall()
    for video_id, filename in videos:
        if filename is None:
            continue


        date_match = re.search(r"^(\d{8}) - ", filename)
        if date_match:
            new_date = date_match.group(1)
            new_date_formatted = f"{new_date[:4]}-{new_date[4:6]}-{new_date[6:8]}"
            if not update_video_date_on_peertube(instance_url, access_token, video_id, new_date_formatted):
                print(f"Failed to update date for video {video_id}")

    conn.commit()

    cursor.execute("SELECT id, original_publish_date FROM peertube_videos WHERE original_publish_date IS NOT NULL")
    videos = cursor.fetchall()

    success_count = 0
    failure_count = 0
    skipped_count = 0

    for video_id, local_date in videos:
        video_info = get_video_info_from_peertube(instance_url, access_token, video_id)
        if video_info is None:
            print(f"Failed to fetch info for video {video_id}")
            failure_count += 1
            continue

        if video_info.get("originallyPublishedAt") is not None:
            # print(f"Skipping video {video_id} as it already has an original publish date")
            skipped_count += 1
            continue

        if update_video_date_on_peertube(instance_url, access_token, video_id, local_date):
            # print(f"Successfully updated date for video {video_id} to {local_date}")
            success_count += 1
        else:
            print(f"Failed to update date for video {video_id}")
            failure_count += 1

    print(f"\nUpdate complete. Successes: {success_count}, Failures: {failure_count}, Skipped: {skipped_count}")


if __name__ == "__main__":
    instance_url = "https://peertube.nodja.com"
    load_dotenv()

    username = os.getenv("PEERTUBE_USERNAME")
    password = os.getenv("PEERTUBE_PASSWORD")

    client_id, client_secret = get_client_credentials(instance_url)
    access_token = get_user_token(instance_url, client_id, client_secret, username, password)

    conn = create_database()

    update_dates_on_peertube(conn, instance_url, access_token)

    all_videos = get_all_videos(instance_url, access_token, conn)
    for video in all_videos:
        insert_or_update_video(conn, video)

    print(f"Total videos processed: {len(all_videos)}")

    conn.close()
