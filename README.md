# Commnad-line Program Youtube Music Channel Scraper

This program scrapes the given Youtube music channels by fetching infomation of videos, and saving information and videos into local drives. The program are currently only avaiable for downloading artwork images (if applicable), thumbnails, audios (mp3 format) and videos.

## Features

### Automatically Resume Scraping and Downloading Processes.
Normally, scraping a big music channel (e.g., MrSuicideSheep) could take hours (or even longer) as the channel contains over thousands of videos.
Thus the scraping and downloading process could be easily interrupted by anything, for example, power failure or poor internet connection, or coffee leak (even worse :) ).

Here the information scraping and video downloading are seperately treated.

To automatically resume the information scraping process, this program will deal with this problem by checking the number of videos (after stop_upload_time if applicable) of two files: FILE1. "channel_videos_id_list.txt" and FILE2."channel_videos_info_list.json"
FILE1 will store all video_ids from one channel, which only takes minutes to scrape and save.
FILE2 will store all video_info (including URL, title, upload_date, chapters, thumbnail, artwork_url, etc), which will be used for downloading. Saving this file could take around mins or hours depends on how many videos that channel has.

There are three senarios in resume scheme: 
     1. both files are created, then check the number of recored videos,
        if   	the numbers are equal, then no more infomartion fetch process.
        else 	resume the information fetch process from the last video id in FILE2.
            	       
     2. FILE2 not exists but FILE1 exists, then resume the infomation fetch process and create FILE2.
            	
     3. both files are not created, then start the infomation fetch process straightforward.

To automatically resume the video downloading process, this program will deal with this problem by checking the number of files under one video folder.
For videos without chapters, the file number under a video folder should be the number of items downloaded. For example, usually, the files of a video folder should contains an artwork image (if recorded under the same video title in "channel_videos_info_list.json"), a thumbnail and a video file, thus if file number is lower than 3, then the downloading process will resume from downloading the files not exist. For videos with chapters, the file number should be 3 + number of chapters. If the number of files is lower than that, the downloading process will resume from downloading the files not exist.


### Automatically Rename Video Titles (Optional)

During the development, an interesting problem is observed that the video titles could contain some weird words or symbols which are not able to be file titles saved in disk (especially for Linux OS). Further more, the titles are abitrary sometimes, which are difficult to extract useful information, for example,  artist names, features, music or song titles and types of video contents (e.g., mv or lyric video or visualizer, etc.). Thus, here presents a rename scheme that will automatically rename the video titles into a unified format:
"[artist names] - [song_titles] {(feat. [artist names]) or (with [artist names] or ([artist names] cover) or ([artist names] remix) or ([xxx] version)} {(NCS Release)}
where the words in bracket "[]" are essential while the words in bracket "{}" are optional.

### Update Channels Already Scraped
Setting up flag "--update True" when running program will automatically update these two files: "channel_videos_id_list.txt" and "channel_videos_info_list.json", and download new videos.

### Setups

1. Please install youtube-dl for video (or audio) downloading.
2. Please install all the other necessary libraries in "requirements.txt" before starting the program.
3. (Optional) An adblock plugin could be installed via Firefox browser as this will disable the ads when scraping the video webpage (save times).


## Examples

### Example 1: Scrape youtube channels
python youtube_scraper_by_given_artist_channels.py \
       --music_channel_list_filepath [path/to/channel_list.txt]\
       --saved_path [path/to/saved_path]\
       --download_file_format [file_format]
       
Running this example, a folder will be created if saved_path not exists, then "channel_videos_id_list.txt" and "channel_videos_info_list.json" will be created under the same youtube channel folder, next a folder (named as the video_id) will be created for each downloaded video, in which all related images (e.g., artwork images and thumbnails) and videos (or audios) will be downloaded from Youtube.

### Example 2: Update youtube channels which are already scraped
python youtube_scraper_by_given_artist_channels.py \
       --music_channel_list_filepath [path/to/channel_list.txt]\
       --saved_path [path/to/saved_path]\
       --download_file_format [file_format]
       --update True
       
Running this example, channels that already scraped and downloaded will be updated by re-scraping the information of channels, and downloading new videos. 
