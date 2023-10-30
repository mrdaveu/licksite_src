import functions_framework
import pickle
import os
import re
import io
import requests
import yt_dlp
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload
from tqdm import tqdm
from flask import escape, request
from yt_dlp import YoutubeDL
from github import Github


g = Github('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')
repo = g.get_repo('mrdaveu/licksite')

SCOPES = ['https://www.googleapis.com/auth/drive.metadata',
          'https://www.googleapis.com/auth/drive',
          'https://www.googleapis.com/auth/drive.file'
          ]

@functions_framework.http
def hello_http(request):
    def get_gdrive_service():
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        # initiate Google Drive service API
        return build('drive', 'v3', credentials=creds)


    def download_file_from_google_drive(id, destination):
        def get_confirm_token(response):
            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    return value
            return None

        def save_response_content(response, destination):
            CHUNK_SIZE = 32768
            # get the file size from Content-length response header
            file_size = int(response.headers.get("Content-Length", 0))
            # extract Content disposition from response headers
            content_disposition = response.headers.get("content-disposition")
            # parse filename
            filename = re.findall("filename=\"(.+)\"", content_disposition)[0]
            print("[+] File size:", file_size)
            print("[+] File name:", filename)
            progress = tqdm(response.iter_content(CHUNK_SIZE), f"Downloading {filename}", total=file_size, unit="Byte", unit_scale=True, unit_divisor=1024)
            with open(destination, "wb") as f:
                for chunk in progress:
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
                        # update the progress bar
                        progress.update(len(chunk))
            progress.close()
        # base URL for download
        URL = "https://docs.google.com/uc?export=download"
        # init a HTTP session
        session = requests.Session()
        # make a request
        response = session.get(URL, params = {'id': id}, stream=True)
        print("[+] Downloading", response.url)
        # get confirmation token
        token = get_confirm_token(response)
        if token:
            params = {'id': id, 'confirm':token}
            response = session.get(URL, params=params, stream=True)
        # download to disk
        save_response_content(response, destination)


    def download(gdrive_link, id):
        service = get_gdrive_service()
        # the name of the file you want to download from Google Drive 
        filename = id
        # search for the file by name
        # get the GDrive ID of the file
        file_id = gdrive_link
        # make it shareable
        service.permissions().create(body={"role": "reader", "type": "anyone"}, fileId=file_id).execute()
        # download file
        download_file_from_google_drive(file_id, id)
        with open(id, 'r') as file:
            data = file.read()
        repo.create_file(id, 'testbed', data, branch='main')

    def ytcrop(yt_url, start, end, id):	
        ydl_opts = {
            'format': 'm4a/bestaudio/best',
            'outtmpl': id, 
            'postprocessor_args': ['-ss', start, '-to', end],
            'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }]
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download(yt_url)
        with open(id, 'rb') as file:
            data = file.read()
        repo.create_file(id, 'testbed', data, branch='main')

    request_args = request.args

    if request_args and "yt_url" in request_args:
        name = request_args["yt_url"]
        musicxml_id = request_args["id"] + '.musicxml'
        id = request_args["id"] + '.m4a'
        start = request_args["start"]
        end = request_args["end"]
        gdrive_link = request_args["gdrive_url"].split('=')[-1]
        yt_url = request_args["yt_url"]
        
        download(gdrive_link, musicxml_id)
        ytcrop(yt_url, start, end, id)
    else:
        name = "World"
    return f"Hellooooo {escape(name)}!"