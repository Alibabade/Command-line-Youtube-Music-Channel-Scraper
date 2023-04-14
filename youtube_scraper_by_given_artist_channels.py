import os
import sys
import time
import argparse
from tqdm import tqdm

from lib.Utils import *
from lib.Youtube_Scraper_API import youtube_music_channel_scraper_api

"""
Scrape all video information and download all the videos of given Youtube channels.
"""

class scraper_by_given_artist_channels:
    name = "scraper_by_given_artist_channels"

    def __init__(self, args, ):
        self.youtube_scraper_api = youtube_music_channel_scraper_api(args)

    def _process(self, channel_url):
        self.youtube_scraper_api.download_youtube_channel(channel_url)


    def start(self):
        print(f"start to scrape youtube by given channels...")
        start_time_total = time.time()

        # read channel infos (mostly are channel urls) from txt file, 
        # then put them in a list called channel_info_list.
        channel_info_list = []
        with open(self.youtube_scraper_api.list_filepath, 'r') as f:
            lines = f.readlines()
            channel_urls = []
            
            for line in lines:
                channel_url = line.replace('\n','').split(': ')[-1]
                channel_urls.append(channel_url)



        resume_idx = 0
        if resume_idx > 0:
            print(f"  resume processing {resume_idx}/{len(channel_urls)}th given channel: {channel_urls[resume_idx]}")

        start_time = time.time()
        for idx in pit(range(resume_idx,len(channel_urls)), text="Given music channels", color="blue"):

            channel_url = channel_urls[idx]
            self._process(channel_url)
            a
            
            execution_time = time.time() - start_time
            
            """
            Processing the scraper program over 50 mins could provoke the 
            triger that Youtube detect and recognise the scraper then ban
            the program, thus the following code is a trick for long running 
            which pauses the scraper for 100 seconds when total running time 
            is over 50 mins.
            Mostly time it should be working.
            """
            # long pause when scraper works over 50 mins
            # otherwise, short pause
            if execution_time / 60 > 50:
                pause_report(length=100, file_count=None,disp=False)
                start_time = time.time()
            else:
                pause_report(length=10,file_count=None,disp=False)

        execution_time = (time.time() - start_time_total)/60
        
        print(f"The youtube scraper by given artists executes : {round(execution_time,2)} min")


def main():
    music_channel_list_filepath = "../youtube_music_channel_list.txt"
    saved_path = "../data/given_music_channels/"
    download_file_format = 'mp3'
    
    parser = argparse.ArgumentParser(description='parser for youtube music channel scraper')
    parser.add_argument("--music_channel_list_filepath",  default="../youtube_music_channel_list.txt")
    parser.add_argument("--saved_path",  default="../data/given_music_channels/")
    parser.add_argument("--download_file_format",  default="mp3")
    parser.add_argument("--update",  default=True) # update already scraped channels
    parser.add_argument("--adblock_add_on_path",  default=None,
                        help="path to adblock plugin")
    
    parser.add_argument("--stop_upload_date",  default="11 Apr 2023")
    parser.add_argument("--stop_video_id",  default=None)
    parser.add_argument("--rename_title",  default=True)
    parser.add_argument("--detail_disp",  default=False)
    parser.add_argument("--firefoxOptions",  default=None,
                        help="choose from [None, headless]")
    
    
    args = parser.parse_args()
    scraper_instance = scraper_by_given_artist_channels(args)

    scraper_instance.start()

if __name__ == "__main__":
    main()
