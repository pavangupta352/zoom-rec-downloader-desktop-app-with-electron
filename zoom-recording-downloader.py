# system libraries
import base64
import datetime
import json
import os
import re as regex
import signal
import sys as system
import sys
import time

# installed libraries
import dateutil.parser as parser
import pathvalidate as path_validate
import requests
import tqdm as progress_bar
from tqdm import tqdm


LAST_TOKEN_REFRESH_TIME = datetime.datetime.now()
AUTHORIZATION_HEADER = {}


def save_access_token(access_token, expires_in):
    expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
    with open('access_token.json', 'w') as file:
        json.dump({'access_token': access_token,
                  'expiry_time': expiry_time.isoformat()}, file)


def load_access_token_from_file():
    with open('access_token.json', 'r') as file:
        token_data = json.load(file)
        return token_data['access_token']


CONF_PATH = "zoom-recording-downloader.conf"
with open(CONF_PATH, encoding="utf-8-sig") as json_file:
    CONF = json.loads(json_file.read())

ACCOUNT_ID = CONF["OAuth"]["account_id"]
CLIENT_ID = CONF["OAuth"]["client_id"]
CLIENT_SECRET = CONF["OAuth"]["client_secret"]

APP_VERSION = "3.0 (OAuth)"

API_ENDPOINT_USER_LIST = "https://api.zoom.us/v2/users"

RECORDING_START_YEAR = datetime.date.today().year
RECORDING_START_MONTH = 1
RECORDING_START_DAY = 1
RECORDING_END_DATE = datetime.date.today()
DOWNLOAD_DIRECTORY = 'X:\\Upwork\\Antonio\\Downloads of zoom recordings'
COMPLETED_MEETING_IDS_LOG = 'completed-downloads.log'
COMPLETED_MEETING_IDS = set()


class Color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARK_CYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def is_token_expired():
    with open('access_token.json', 'r') as file:
        token_data = json.load(file)
        expiry_time = datetime.datetime.fromisoformat(
            token_data['expiry_time'])
        return datetime.datetime.now() >= expiry_time


def get_access_token():
    if not os.path.exists('access_token.json') or is_token_expired():
        request_new_access_token()
    return load_access_token_from_file()


def request_new_access_token():
    global ACCESS_TOKEN, AUTHORIZATION_HEADER, LAST_TOKEN_REFRESH_TIME
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ACCOUNT_ID}"
    client_cred = f"{CLIENT_ID}:{CLIENT_SECRET}"
    client_cred_base64_string = base64.b64encode(
        client_cred.encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {client_cred_base64_string}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response = requests.request("POST", url, headers=headers)
    response_json = json.loads(response.text)
    try:
        ACCESS_TOKEN = response_json["access_token"]
        # Default to 1 hour if not provided
        expires_in = response_json.get("expires_in", 3600)
        AUTHORIZATION_HEADER = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        save_access_token(ACCESS_TOKEN, expires_in)
        LAST_TOKEN_REFRESH_TIME = datetime.datetime.now()
    except KeyError as e:
        print(
            f"{Color.RED}### Error in response: {e}, Response: {response.text}{Color.END}")


def load_access_token():
    global ACCESS_TOKEN, AUTHORIZATION_HEADER, LAST_TOKEN_REFRESH_TIME
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ACCOUNT_ID}"
    client_cred = f"{CLIENT_ID}:{CLIENT_SECRET}"
    client_cred_base64_string = base64.b64encode(
        client_cred.encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {client_cred_base64_string}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response = requests.request("POST", url, headers=headers)
    response_json = json.loads(response.text)
    try:
        ACCESS_TOKEN = response_json["access_token"]
        AUTHORIZATION_HEADER = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        save_access_token(ACCESS_TOKEN)  # Updated this line
        LAST_TOKEN_REFRESH_TIME = datetime.datetime.now()
    except KeyError as e:
        print(
            f"{Color.RED}### Error in response: {e}, Response: {response.text}{Color.END}")


def get_users():
    """ loop through pages and return all users
    """
    response = requests.get(url=API_ENDPOINT_USER_LIST,
                            headers=AUTHORIZATION_HEADER)

    if not response.ok:
        print(response)
        print(
            f"{Color.RED}### Could not retrieve users. Please make sure that your access "
            f"token is still valid{Color.END}"
        )

        system.exit(1)

    page_data = response.json()
    total_pages = int(page_data["page_count"]) + 1

    all_users = []

    for page in range(1, total_pages):
        url = f"{API_ENDPOINT_USER_LIST}?page_number={str(page)}"
        user_data = requests.get(url=url, headers=AUTHORIZATION_HEADER).json()
        users = ([
            (
                user["email"],
                user["id"],
                user["first_name"],
                user["last_name"]
            )
            for user in user_data["users"]
        ])

        all_users.extend(users)
        page += 1

    return all_users


def format_filename(params):
    file_extension = params["file_extension"]
    recording = params["recording"]
    recording_id = params["recording_id"]
    recording_type = params["recording_type"]

    invalid_chars_pattern = r'[<>:"/\\|?*\x00-\x1F]'
    topic = regex.sub(invalid_chars_pattern, '', recording["topic"])
    rec_type = recording_type.replace("_", " ").title()
    meeting_time = parser.parse(recording["start_time"]).strftime(
        "%Y.%m.%d - %I.%M %p UTC")

    return (
        f"{meeting_time} - {topic} - {rec_type} - {recording_id}.{file_extension.lower()}",
        f"{topic} - {meeting_time}"
    )


def get_downloads(recording):
    if not recording.get("recording_files"):
        raise Exception

    downloads = []
    for download in recording["recording_files"]:
        file_type = download["file_type"]
        file_extension = download["file_extension"]
        recording_id = download["id"]

        if file_type == "":
            recording_type = "incomplete"
        elif file_type != "TIMELINE":
            recording_type = download["recording_type"]
        else:
            recording_type = download["file_type"]

        # must append access token to download_url
        download_url = f"{download['download_url']}?access_token={ACCESS_TOKEN}"
        downloads.append((file_type, file_extension,
                         download_url, recording_type, recording_id))

    return downloads


def get_recordings(email, page_size, rec_start_date, rec_end_date):
    return {
        "userId": email,
        "page_size": page_size,
        "from": rec_start_date,
        "to": rec_end_date
    }


def per_delta(start, end, delta):
    """ Generator used to create deltas for recording start and end dates
    """
    curr = start
    while curr < end:
        yield curr, min(curr + delta, end)
        curr += delta


def list_recordings(email):
    """ Start date now split into YEAR, MONTH, and DAY variables (Within 6 month range)
        then get recordings within that range
    """
    recordings = []

    for start, end in per_delta(
        datetime.date(RECORDING_START_YEAR,
                      RECORDING_START_MONTH, RECORDING_START_DAY),
        RECORDING_END_DATE,
        datetime.timedelta(days=30)
    ):
        post_data = get_recordings(email, 300, start, end)
        response = requests.get(
            url=f"https://api.zoom.us/v2/users/{email}/recordings",
            headers=AUTHORIZATION_HEADER,
            params=post_data
        )
        recordings_data = response.json()
        recordings.extend(recordings_data["meetings"])

    return recordings


def download_recording(download_url, email, filename, folder_name):
    dl_dir = os.sep.join([DOWNLOAD_DIRECTORY, folder_name])
    sanitized_download_dir = path_validate.sanitize_filepath(dl_dir)
    sanitized_filename = path_validate.sanitize_filename(filename)
    full_filename = os.sep.join([sanitized_download_dir, sanitized_filename])

    os.makedirs(sanitized_download_dir, exist_ok=True)

    response = requests.get(download_url, stream=True)
    total_size = int(response.headers.get("content-length", 0))
    block_size = 32 * 1024  # 32 Kibibytes

    downloaded = 0
    start_time = time.time()

    print(f"Starting download: {filename}")

    try:
        with open(full_filename, "wb") as fd:
            for chunk in response.iter_content(block_size):
                size = fd.write(chunk)
                downloaded += size

                # Calculate progress and speed
                progress = (downloaded / total_size) * 100
                elapsed_time = time.time() - start_time
                speed = downloaded / (elapsed_time * 1024)  # speed in KiB/s

                # Only send progress to Electron app, not print in terminal
                print(f"electron_progress:{progress:.2f}%,{speed:.2f}KiB/s")

        print(f"Completed download: {filename}")
        return True
    except Exception as e:
        print(f"{Color.RED}### Error: {e}{Color.END}")
        return False


def load_completed_meeting_ids():
    try:
        with open(COMPLETED_MEETING_IDS_LOG, 'r') as fd:
            [COMPLETED_MEETING_IDS.add(line.strip()) for line in fd]

    except FileNotFoundError:
        print(
            f"{Color.DARK_CYAN}Log file not found. Creating new log file: {Color.END}"
            f"{COMPLETED_MEETING_IDS_LOG}\n"
        )


def main():
    # clear the screen buffer
    os.system('cls' if os.name == 'nt' else 'clear')

    # show the logo
    print(f"""
        {Color.DARK_CYAN}

                        Zoom Recording Downloader made by Pavan

                            Version {APP_VERSION}

        {Color.END}
    """)

    try:
        ACCESS_TOKEN = get_access_token()
        AUTHORIZATION_HEADER = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
    except FileNotFoundError:
        # If tokens file does not exist, get a new access token
        request_new_access_token()

    load_completed_meeting_ids()

    print(f"{Color.BOLD}Getting user accounts...{Color.END}")
    users = get_users()

    for email, user_id, first_name, last_name in users:
        userInfo = (
            f"{first_name} {last_name} - {email}" if first_name and last_name else f"{email}"
        )
        print(f"\n{Color.BOLD}Getting recording list for {userInfo}{Color.END}")

        recordings = list_recordings(user_id)
        total_count = len(recordings)
        print(f"==> Found {total_count} recordings")

        for index, recording in enumerate(recordings):
            success = False
            meeting_id = recording["uuid"]
            if meeting_id in COMPLETED_MEETING_IDS:
                print(f"==> Skipping already downloaded meeting: {meeting_id}")

                continue

            try:
                downloads = get_downloads(recording)
            except Exception:
                print(
                    f"{Color.RED}### Recording files missing for call with id {Color.END}"
                    f"'{recording['id']}'\n"
                )

                continue

            for file_type, file_extension, download_url, recording_type, recording_id in downloads:
                if recording_type != 'incomplete':
                    filename, folder_name = (
                        format_filename({
                            "file_type": file_type,
                            "recording": recording,
                            "file_extension": file_extension,
                            "recording_type": recording_type,
                            "recording_id": recording_id
                        })
                    )

                    # truncate URL to 64 characters
                    truncated_url = download_url[0:64] + "..."
                    print(
                        f"==> Downloading ({index + 1} of {total_count}) as {recording_type}: "
                        f"{recording_id}: {truncated_url}"
                    )
                    success |= download_recording(
                        download_url, email, filename, folder_name)

                else:
                    print(
                        f"{Color.RED}### Incomplete Recording ({index + 1} of {total_count}) for "
                        f"recording with id {Color.END}'{recording_id}'"
                    )
                    success = False

            if success:
                # if successful, write the ID of this recording to the completed file
                with open(COMPLETED_MEETING_IDS_LOG, 'a') as log:
                    COMPLETED_MEETING_IDS.add(meeting_id)
                    log.write(meeting_id)
                    log.write('\n')
                    log.flush()

    print(f"\n{Color.BOLD}{Color.GREEN}*** All done! ***{Color.END}")
    save_location = os.path.abspath(DOWNLOAD_DIRECTORY)
    print(
        f"\n{Color.BLUE}Recordings have been saved to: {Color.UNDERLINE}{save_location}"
        f"{Color.END}\n"
    )


if __name__ == "__main__":
    # Log script initialization
    print("Python script initialized. Awaiting commands...")

    try:
        while True:
            line = sys.stdin.readline().strip()
            print(f"Received command: '{line}'")  # Log received command

            if line == "start":
                main()
                break
            elif line == "close-app":
                print("Exiting script.")
                break
    except KeyboardInterrupt:
        print("Exiting script due to KeyboardInterrupt.")
