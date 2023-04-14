import os
import sys
import time
import re
import json
import requests
import youtube_dl
import html_to_json
import pandas as pd
from tqdm import tqdm
from selenium import webdriver
from pydub import AudioSegment
from requests.adapters import HTTPAdapter
from selenium.webdriver import FirefoxOptions
from datetime import datetime, timedelta
from Utils import *
"""
This script aims to provide functions to download videos from given 
Youtube channels.
There are a few core funcions for option:
1. extract channel id and channel name from channel url
2. extract all video infos which includes:
    1). video title 		str
    2). video id		str
    3). video_upload_date	datetime object
    4). video_duration:		str
    5). thumbnail_url: 		str, end in ".webp" or ".jpg"
    6). artwork_url:  		str or None, like original artwork image for backgroud
    7). chapters:		dict if video has, contains title,start_time,end_time
3. download artworks
4. download thumbnails
5. download videos (or convert it to mp3) by youtube-dl
6. download video chapters (or convert them into mp3) by youtube-dl and FFMPEG (or AudioSegment) (optional)
   The process of video splited into chapters will not involve any encoding and decoding process in FFMPEG.

Notice: no Shorts or Premiered videos will be downloaded by default, 
        and currently only 'mp3' format is supported for audio download.


Two optional variables that control the fetch process:
1. stop_upload_date, only videos uploaded time after this date
                        will be downloaded. This is optional.
2. stop_video_id,    only videos uploaded time after this video's
                        will be downloaded. This is optional.
3. rename_title,     rename video titles for a unified format.

4. update,           update channel information, and download new
                        videos
"""


class youtube_music_channel_scraper_api:
    name = "youtube_music_channel_scraper_api"
    
    threads = 1 #cpu_count() * 3

 
    def __init__(self, args):
    
        self.list_filepath = args.music_channel_list_filepath
        self.download_file_format = args.download_file_format
        self.saved_path = args.saved_path
        

        #############optional for scraping and downloading processes############3

        # only download videos which are uploaded after this date
        self.stop_upload_date = args.stop_upload_date # e.g.,'11 Mar 2023' 
        # only download videos which are uploaded after this video_id
        self.stop_video_id = args.stop_video_id #'mpXkkqWK7wg'   
        # rename the video titles for music videos
        self.rename_title = args.rename_title
        
        self.detail_disp = args.detail_disp
        
        self.update = args.update
        
        # add adblock plugin into webdriver.Firefox, which disable ads when browsering
        self.adblock_add_on_path = args.adblock_add_on_path 
        
        self.channel_ids_set = set()
        
        self.opts = FirefoxOptions()
        if args.firefoxOptions == 'headless':
            self.opts.add_argument("--headless") 
        
        if self.saved_path:
            if not os.path.exists(self.saved_path):
                os.makedirs(self.saved_path)
        
        
    ######some functions can be used outside directly#############################################################    
    def get_channel_ids(self):
        return self.channel_ids_set
        
    def add_channel_id(self, channel_id):
        self.channel_ids_set.add(channel_id)    
        
        
    #################################utils#######################################################################  
    def _scroll2bottom_webpage(self, driver):
        # scroll down the bottom of the youtube webpage, normaly it's channel video page.
        height = driver.execute_script("return document.documentElement.scrollHeight")
        lastheight = 0
        
        while True:     
            if lastheight == height:
                break
            lastheight = height
            driver.execute_script("window.scrollTo(0, " + str(height) + ");") 
            time.sleep(5)
            height = driver.execute_script("return document.documentElement.scrollHeight")
            
             
    def _extract_channel_id(self, driver):
        print(f"    extract channel id ...")
       
        time.sleep(3)
        data = driver.find_element_by_xpath('/html/body/meta[5]')
        if self.detail_disp:
            print(f"data.get_attribute('content'): {data.get_attribute('content')}")
        channel_id = data.get_attribute('content').split('/')[-1]
        print(f"    channel_id: {channel_id}")

        return channel_id
        
    def _fetch_webpage_in_json_format(self, url):
        
        """
        Aims to fetch the useful json value from webpage
        for artwork download, e.g., artstation and pixiv.
    
        Notice:
            There is a weird thing that the info that web driver gets from
            url doesn't always contain useful ones, thus here adds a while loop
            to filter out useless web scrape results.
        """

        #opts = FirefoxOptions()
        #opts.add_argument("--headless")
        driver = webdriver.Firefox(firefox_options=self.opts)
        count = 50
        while True:
            try:
                driver.get(url)
                html = driver.page_source
                json_text = html_to_json.convert(html)  
            
                txt = json_text['html'][0]['body'][0]['div'][0]['div'][0]#['_value']#['div'][0]

                if '_value' in txt.keys():
                    json_value = json.loads(txt['_value'])
                    break
            except:
                count -= 1
                time.sleep(5)
                if count < 0:
                    json_value = None
                    break
                continue
           
        driver.close()    
        return json_value
        
        
        
    def _get_img_content_from_url(self, url, client, website='pixiv'):
        # website could be "artstation", "pixiv", 
        #                  "pexels", 'unsplash', 'deviant', 'flickr'
        try_count = 50
        while True:
            try:
                if website == 'artstation':
                    res = requests.get(url).content
                if website == 'pixiv':
                    res = client.get(url, stream=True)
                else:
                    res = client.get(url)
                break
            except:
                try_count -= 1
                if try_count < 0:
                    print(f"Error: image can not be downloaded from {url}, fail to download artwork.")
                    res = None
                    break
                time.sleep(5)         
        return res
        
    def _get_content_from_url(self, driver, url):
        while True:
            try:
                driver.get(url)
                break
            except:
                time.sleep(5)
            
    def _convert_time2millionseconds(self, t):
        hours = t.split(':')[0]
        mins = t.split(':')[1]
        secs = t.split(':')[2]
        millsecs = int(hours) * 60 * 60 * 1000 +\
                   int(mins) * 60 * 1000 +\
                   int(secs) * 1000
        return millsecs  
        
    def split_audio_file(self, audio_path, start_time, end_time, saved_path):
        # start_time and end_time in millionseconds
        #print('split audio file...')
        sound = AudioSegment.from_mp3(audio_path)
        extract = sound[start_time:end_time]
        extract.export(saved_path)
        
    ############################################################################################################################## 
    ##################################################image downloader############################################################
    ############################################################################################################################## 
            
    def _download_artstation_artwork(self, hash_id, img_save_folder):
    
        #print(f"hash_id: {hash_id}")
        if isinstance(hash_id, str):
            img_json_url = f"https://www.artstation.com/projects/{hash_id}.json" 
            json_data = self._fetch_webpage_in_json_format(img_json_url)
            if json_data is None:
                print(f"    cound not open {img_json_url}, stop download artwork.")
                return 
            df = pd.DataFrame(json_data['assets'])
            media_urls= []
            media_urls.append(df['image_url'][0])

        elif isinstance(hash_id, list):         
            img_json_url = f"https://www.artstation.com/projects/{hash_id[0]}.json"
            json_data = self._fetch_webpage_in_json_format(img_json_url)
            if json_data is None:
                print(f"    cound not open {img_json_url}, stop download artwork.")
                return 
            df = pd.DataFrame(json_data['assets'])
            media_urls= []
            for asset_idx in hash_id[1:]:
                media_urls.append(df['image_url'][asset_idx])

    
                
        for idx in range(len(media_urls)):
            media_url = media_urls[idx]
            # it is able to download jpg, png and gif file.
            media_type = media_url.split('?')[-2][-4:]
            if isinstance(hash_id, str):
                file_name = hash_id
            elif isinstance(hash_id, list):
                if idx == 0:
                    file_name = f"{hash_id[0]}"
                else:
                    file_name = f"{hash_id[0]}_{hash_id[1:][idx]}"

            if media_type == '.jpg' :               
                media_save_filename = os.path.join(img_save_folder, file_name+".jpg").replace('\r','')
            elif media_type=='.png':
                media_save_filename = os.path.join(img_save_folder, f"{file_name}.png")
            elif media_type == '.gif':
                media_save_filename = os.path.join(img_save_folder, f"{file_name}.gif")
                
            
            if os.path.exists(media_save_filename):
                if self.detail_disp:
                    print(f"    image: {media_save_filename} exist, skip to next")
                return
                     
            with open(media_save_filename,'wb') as f:   
                img_content = self._get_img_content_from_url(media_url ,None, 'artstation')        
                if img_content is not None:
                    f.write(img_content)
                if self.detail_disp:
                    print(f"    download: {media_save_filename}")
                
                       
    def _download_pixiv_artwork(self, artwork_id, user_artworks_saved_path):
        
        def _get_download_url(artwork_id):
            url = f"https://www.pixiv.net/ajax/illust/{artwork_id}"

            json_value = self._fetch_webpage_in_json_format(url) 
            if json_value is None:
                return   
            json = json_value["body"]
            if not isinstance(json, dict):
                return 
            img_url = json["urls"]["original"]

            return img_url
        
        
        url = _get_download_url(artwork_id)
        if url is None:
            print(f"    cound not open {url}, stop download artwork.")
            return  
        headers = {"referer": f"https://www.pixiv.net/member_illust.php?mode=medium&illust_id={artwork_id}"}
        client = requests.Session()
        client.headers.update(headers)
 
        res = self._get_img_content_from_url( url, client)
        #res = client.get(url, stream=True)
        #res = self.client.get(url)
        if res is None:
            return 
        file_name = re.search(r"\d+_(p|ugoira).*?\..*", url)[0]

        artwork_saved_path = os.path.join(user_artworks_saved_path, file_name)
        if os.path.exists(artwork_saved_path):
            if self.detail_disp:
                print(f"    {artwork_saved_path} exists, skip to next.")
            return
        with open(artwork_saved_path, 'wb') as f:
            f.write(res.content)
            if self.detail_disp:
                print(f"    downloaded in user_artworks_saved_path: {file_name}")

    
                
    def _download_unsplash_image(self, url, saved_path):
        
        image_name = url.split('/')[-1] + '.jpg'
        image_saved_path = os.path.join(saved_path, image_name)
        if os.path.exists(image_saved_path):
            print(f"    unsplash image has been downloaded, skip to next...")
            return
        
        driver = webdriver.Firefox(firefox_options=self.opts) 
        self._get_content_from_url(driver, url)
        html = driver.page_source
        
        # find the image url
        target_str = "srcSet=\""
        start_idx = html.find(target_str) + len(target_str)
        end_idx = html.find("\"", start_idx)
        img_urls = html[start_idx:end_idx].split(', ')
        assert isinstance(img_urls, list)
        print(f"img_urls[-1]: {img_urls[-1]}")
        
        
        client = requests.Session()
        #client.headers.update(headers)
   
        res = self._get_img_content_from_url(url, client, 'unsplash')
        
        if res is None:
            return
        
        with open(image_saved_path, 'wb') as f:
            f.write(res.content)
            if self.detail_disp:
                print(f"    downloaded unsplash image at: {image_saved_path}")
                
    
    
    def _download_pexels_or_deviant_or_flickr_image(self, url, saved_path):
        image_name = url.split('/')[-1].split('-')[-1] + '.jpg' if '-' in url else url.split('/')[-1] + '.jpg'
        image_saved_path = os.path.join(saved_path, image_name)
        if os.path.exists(image_saved_path):
            print(f"    pexels image has been downloaded, skip to next...")
            return
        
        driver = webdriver.Firefox(firefox_options=self.opts) 
        self._get_content_from_url(driver, url)
        html = driver.page_source
        
        # find the image url
        target_str = "property=\"og:image\" content=\""
        start_idx = html.find(target_str) + len(target_str)
        print(f"html[start_idx]: {html[start_idx]}")
        #assert 1 == 0
        end_idx = html.find("\"", start_idx)
        print(f"html[start_idx:end_idx]: {html[start_idx:end_idx]}")
        img_url = html[start_idx:end_idx]
        assert isinstance(img_url, str)
        #print(f"img_urls[-1]: {img_urls[-1]}")
        
        
        client = requests.Session()
        #client.headers.update(headers)   
        res = self._get_img_content_from_url( url, client, 'pexels')
        
        if res is None:
            return
        
        with open(image_saved_path, 'wb') as f:
            
            f.write(res.content)
            if self.detail_disp:
                print(f"    downloaded image at: {image_saved_path}")    
                
    ##############################################################################################################################            
    #######################################################################end of image downloader################################            
    ############################################################################################################################## 
    
    
    def _download_artwork_image(self, video_info):
            print(f"    download artwork ...")
            if 'artstation.com/' in video_info["artwork_url"]:
                hash_id = video_info["artwork_url"].split('/')[-1]
                self._download_artstation_artwork(hash_id, saved_path)
            elif "pixiv.net/" in video_info["artwork_url"]:
                artwork_id = video_info["artwork_url"].split('/')[-1]
                self._download_pixiv_artwork(artwork_id, saved_path)
            elif "unsplash.com/photos/" in video_info["artwork_url"]:
                self._download_unsplash_image(video_info["artwork_url"], saved_path)
            elif "pexels.com/photo/" in video_info["artwork_url"]:
                self._download_pexels_or_deviant_or_flickr_image(video_info["artwork_url"], saved_path)
            elif "fav.me/" in video_info["artwork_url"]:
                self._download_pexels_or_deviant_or_flickr_image(video_info["artwork_url"], saved_path)
            elif "flickr.com/photos/" in video_info["artwork_url"] or 'flic.kr/p' in video_info["artwork_url"]:
                self._download_pexels_or_deviant_or_flickr_image(video_info["artwork_url"], saved_path)
            print(f"    finish artwork downloading.")  

    
    def download_youtube_video_as_mp3_chapters(self, ext, video_info, channel_saved_path, download_thumbnail=False):
        """
        Here is a trick for downloading youtube video with chapters
        There is a drawback that the download command usually add extra 
        seconds into chapters[1:], sometimes the extra seconds are added
        to the beginning of music, while sometimes are added to the end.
        There is no obvious way to deal with such problem, thus, here 
        only download the first chapter and discord the rest.
        """
        print(f"    start downloading video ({ext}) with chapters and artwork for video title: {video_info['video_title']}...")
        
        # sometimes the video info only contain video upload time 
        # when the video is "Premiered", thus this kind of video
        # will be skipped for downloading
        if "video_id" not in video_info.keys():
            print(f"Error: video_info: {video_info} is not a proper info, skip to next")
            return 
            
        url = "https://www.youtube.com/watch?v=" + video_info["video_id"]
        saved_path = os.path.join(channel_saved_path, video_info["video_id"])
        if not os.path.exists(saved_path):
            os.makedirs(saved_path)
        
                
        title = video_info['video_title']
        vid = video_info["video_id"]
        
        
        
        chapter_need2save_list = []        
        for idx, chapter in enumerate(video_info["chapters"]):  
            chapter_need2save = {}
            audio_filename = chapter["title"]
            if self.rename_title:
                try:      
                    renamed_title = rename(audio_filename)
                except:
                    print(f"chapter title: {audio_filename}")
                    print(f"Error: title: {title}, contains unrecognised patterns in rename function.")
                    print("original chapter title will be used.")
                    #print(f"Skip to next.")
                    #break
                chapter_need2save['title'] = renamed_title + f"#{vid}" + f".{ext}"
            else:
                chapter_need2save['title'] = audio_filename + f"#{vid}" + f".{ext}"
                
            chapter_need2save["start_time"] = chapter["start_time"]
            chapter_need2save["end_time"] = chapter["end_time"]
           
            chapter_need2save_list.append(chapter_need2save)
               
            
        
        # check if all files are downloaded, if not
        # check which file is not downloaded.       
        filenames = os.listdir(saved_path)
        target_file_counts = len(video_info["chapters"])
        target_file_counts += 1 # this count adds downloaded video
        target_file_counts += 1 if video_info['artwork_url'] is not None else 0
        target_file_counts += 1 if download_thumbnail else 0 
        target_file_counts += 1 if os.path.exists(title+f"#{vid}.{ext}") else 0
        if len(filenames) == target_file_counts:   
            print(f"all files have been downloaded, skip to next")
            return 
        else:
            # this aims to find out which chapter needs to be downloaded  
            for filename in filenames:
                for chapter_need2save in chapter_need2save_list:
                    if filename in chapter_need2save["title"]:
                        chapter_need2save_list.remove(chapter_need2save)  
            skip_video_download = False
            if os.path.exists(title+f"#{vid}.{ext}"):
                    skip_video_download = True 
        
        while True:  
            try:      
                if ext == 'mp3':
                    if not skip_video_download and not download_thumbnail:
                        print(f"    download {ext} only...")
                        command = f"youtube-dl -q -o '{saved_path}/%(title)s#%(id)s.%(ext)s' -x --audio-format {ext} {url}"
                        os.system(command)
                        time.sleep(5)    
                                  
                    elif not skip_video_download and download_thumbnail:
                        print(f"    download {ext} and thumbnail...")
                        command = f"youtube-dl -q -o '{saved_path}/%(title)s#%(id)s.%(ext)s' -x --audio-format {ext} {url} --write-thumbnail"    
                        os.system(command)
                        time.sleep(5)  
                    
                    elif skip_video_download and download_thumbnail:
                        print(f"    download thumbnail only...")
                        command = f"youtube-dl -q --write-thumbnail --skip-download {url}"    
                        os.system(command)
                        time.sleep(5)  
                        
                    for idx, chapter in enumerate(chapter_need2save_list):
                        print(f"    split mp3 file into {idx}th/{len(chapter_need2save_list)} chapter: {chapter}")
                        audio_path = os.path.join(saved_path, title+'#'+vid+f'.{ext}')
                        export_path = os.path.join(saved_path, chapter['title'])
                        start_time = self._convert_time2millionseconds(chapter['start_time'])
                        end_time = self._convert_time2millionseconds(chapter['end_time'])
                        self.split_audio_file(audio_path, start_time, end_time, export_path)
                else:
                
                    if not skip_video_download and not download_thumbnail:
                        command = f"youtube-dl -q -o '{saved_path}/%(title)s#%(id)s.%(ext)s' {ext} {url}"
                        os.system(command)
                        time.sleep(5)    
                                  
                    elif not skip_video_download and download_thumbnail:
                        print(f"    download thumbnail...")
                        command = f"youtube-dl -q -o '{saved_path}/%(title)s#%(id)s.%(ext)s' {ext} {url} --write-thumbnail"    
                        os.system(command)
                        time.sleep(5)
                        
                    elif skip_video_download and download_thumbnail:
                        print(f"    download thumbnail only...")
                        command = f"youtube-dl -q --write-thumbnail --skip-download {url}"    
                        os.system(command)
                        time.sleep(5) 
                        
                    for idx, chapter in enumerate(chapter_need2save_list):
                        print(f"    split video file into {idx}th chapter: {chapter}")
                        input_path = os.path.join(saved_path, title+'#'+vid+'.'+ext)
                        output_path = os.path.join(saved_path, chapter['title'])
                        start_time = self._convert_time2millionseconds(chapter['start_time']) // 1000
                        end_time = self._convert_time2millionseconds(chapter['end_time']) // 1000
                        duration = end_time - start_time
                        command = f"ffmpeg -ss {start_time} -t {duration} -i {input_path} {output_path}"
                        os.system(command)
                        time.sleep(5)
                          
                break
            except: 
                print("something wrong with the downloading, wait for 5 seconds to download again.")
                time.sleep(5)
                continue
                
        if video_info["artwork_url"] is not None:
            self._download_artwork_image(video_info)  
            

        print(f"    finish youtube {ext} and artwork downloading.")
                
        
    def download_youtube_video(self, ext, video_info, channel_saved_path, download_thumbnail=False):
        print(f"    start downloading {ext} and artwork for video title: {video_info['video_title']}...")
        
        # sometimes the video info only contain video upload time 
        # when the video is "Premiered", thus this kind of video
        # will be skipped for downloading
        if "video_id" not in video_info.keys():
            print(f"Error: video_info: {video_info} is not a proper info, skip to next")
            return 
            
        url = "https://www.youtube.com/watch?v=" + video_info["video_id"]
        
        saved_path = os.path.join(channel_saved_path, video_info["video_id"])
        if not os.path.exists(saved_path):
            os.makedirs(saved_path)

                
        title = video_info['video_title']
        vid = video_info["video_id"]

        audio_filename = title #+ f'.{ext}'
                  
        
        if self.rename_title:
            try:
                renamed_title = rename(audio_filename)
            except:
                print(f"Error: title: {title}, contains unrecognised patterns in rename function.")
                print("original title will be used.")
                
                renamed_title = audio_filename
            final_saved_title = renamed_title + f"#{vid}" + f".{ext}"
        else:
            final_saved_title = title + f"#{vid}" + f".{ext}"
 
        saved_filename = os.path.join(saved_path, final_saved_title)
        print(f"    saved_filename: {saved_filename}")
        
        # check if all files downloaded
        filenames = os.listdir(saved_path)
        if download_thumbnail:
            if "artwork_url" in video_info.keys() and video_info['artwork_url'] is not None:
                if len(filenames) == 3:
                    print(f"    all files downloaded, skip to next")
                    return
            else:
                if len(filenames) == 2:
                    print(f"    all files downloaded, skip to next")
                    return
        else:
            if "artwork_url" in video_info.keys() and video_info['artwork_url'] is not None:
                if len(filenames) == 2:
                    print(f"    all files downloaded, skip to next")
                    return
            else:
                if len(filenames) == 1:
                    print(f"    all files downloaded, skip to next")
                    return
        
        
        if os.path.exists(saved_filename):
            #filenames = os.listdir(saved_path)
            # this aims to download artwork image when
            # video is downloaded but artwork image is not.
            # if not return here then the video and thumbnail (if True) will normally be downloaded.
            if "artwork_url" in video_info.keys() and video_info['artwork_url'] is not None:
                if download_thumbnail:
                    if len(filenames) < 3:
                        self._download_artwork_image(video_info)
                        print(f"    file: {final_saved_title} exists, skip to next")
                        return 
                else:
                    if len(filenames) < 2:
                        self._download_artwork_image(video_info)  
                        print(f"    file: {final_saved_title} exists, skip to next")
                        return 
                
            
        old_title = title+f"#{vid}.{ext}"
        old_title = old_title.replace('|', '_')
        old_title = old_title.replace('/', '_').replace("?", '')
        old_saved_filename = os.path.join(saved_path, old_title)
      
        
        while True:
            try:
                if ext == 'mp3' and not download_thumbnail:
                    print(f"    download {ext} only...")
                    os.system(f"youtube-dl -q -o '{saved_path}/%(title)s#%(id)s.%(ext)s' -x --audio-format {ext} {url}")       
                elif ext == 'mp3' and download_thumbnail:
                    print(f"    download {ext} and thumbnail...")
                    os.system(f"youtube-dl -q -o '{saved_path}/%(title)s#%(id)s.%(ext)s' -x --audio-format {ext} {url} --write-thumbnail") 
                else:
                    print(f"    download video in format: {ext}...")
                    os.system(f"youtube-dl -q -o '{saved_path}/%(title)s#%(id)s.%(ext)s' {url}")  
                break
            except: 
                print("something wrong with the downloading, wait for 5 seconds to download again.")
                time.sleep(5)
                continue
                
        if "artwork_url" in video_info.keys() and video_info["artwork_url"] is not None:
            self._download_artwork_image(video_info)  
            
        if old_saved_filename != saved_filename:
            try:
                os.rename(old_saved_filename, saved_filename)
            except:
                pass
        
        print(f"    finish youtube {ext} and artwork downloading.")
        
        
    #####################################fetcher from youtube webpage######################################################################
        
    def _fetch_info_from_html(self, html, str_target):

        start_index = html.find(str_target)
        end_index = start_index + len(str_target)

        pair_symbols = []
        while True :
            if html[end_index] in ['{', '[']:
                pair_symbols.append(html[end_index])
            elif html[end_index] in ['}',']']:
                if html[end_index] == '}':
                    if pair_symbols[-1] == '{':
                        pair_symbols.pop()
                    else:
                        print(f"Error, {html[end_index]} and {pair_symbols[-1]} are not matched!")
                        return
                elif html[end_index] == ']':
                    if pair_symbols[-1] == '[':
                        pair_symbols.pop()
                    else:
                        print(f"Error, {html[end_index]} and {pair_symbols[-1]} are not matched!")
                        return
            if pair_symbols == []:
                break
            else:
                end_index += 1
        end_index += 1
        if self.detail_disp:
            print(f"    found content: {html[start_index + len(str_target):end_index]}")

        return start_index + len(str_target), end_index
    
    def _fetch_video_details(self, html):
             
        start_index, end_index = self._fetch_info_from_html(html, "\"videoDetails\":")
        video_details_json = json.loads(html[start_index:end_index])

        return video_details_json
    
    def _fetch_artwork_link(self, video_details_json):
        if video_details_json is None: 
            return 
        
        video_description = video_details_json['shortDescription'] 
        
        matched = re.findall(r'http(\w*)://(\w.+)', video_description)
        
        links = []
        for match in matched:
            url = f"http{match[0]}://{match[1]}"
            url = url.split(' ')
            for u in url:
                links.append(u)
        # remove duplicate element in links
        links = list( dict.fromkeys(links) )
        
        
        for link in links:
            if 'artstation.com/artwork/' in link:
                return link
            elif 'pixiv.net/' in link and '/artworks/' in link:
                return link
            elif 'unsplash.com/photos/' in link:
                return link
            elif 'pexel.com/photo/' in link:
                return link
            elif "fav.me/" in link:
                return link
            elif "flickr.com/photos/" in link or 'flic.kr/p' in link:
                return link
        return
        
    def _fetch_video_chapters(self, html, lengthSeconds):
        
        start_index, end_index = self._fetch_info_from_html(html, "\"chapters\":")     
        #print(f"start_index: {start_index}, end_index: {end_index}")
        #print(f"html[start_index:end_index]: {html[start_index:end_index]}")
        data_json = json.loads(html[start_index:end_index])
        #print(data_json)
        #sys.exit("Error message")
        assert isinstance(data_json, list)
        
        if len(data_json) == 0:
            print(f"    couldn't find chapters")
            return
        print(f"    fetch video chapters...")
        chapters = []
        for idx, data in enumerate(data_json):
            chapter = {}
            chapter['title'] = data["chapterRenderer"]["title"]['simpleText']
            if idx != len(data_json) -1:
                next_data = data_json[idx+1]
                end_time = int(next_data["chapterRenderer"]["timeRangeStartMillis"])*0.001
            else:
                end_time = int(lengthSeconds)
            start_time = int(data["chapterRenderer"]["timeRangeStartMillis"])*0.001    
            chapter['start_time'] = str(timedelta(seconds=start_time))
            chapter['end_time'] = str(timedelta(seconds=end_time))
            #print(f"chapter['start_time']: {chapter['start_time']}, chapter['end_time']: {chapter['end_time']}")
            #print(f"        idx:{idx},  chapter: {chapter}")
            chapters.append(chapter)
           
        return chapters
            
    
    def _fetch_video_upload_date(self, html):      
        str_target = "\"dateText\":"
        start_index, end_index = self._fetch_info_from_html(html, str_target)
        #start_idx = html.find("\"dateText\":") + 27# {"simpleText":"29 Apr 2018"}
        #end_idx = start_idx + 
        #print(f"    start_index: {start_index}, end_index: {end_index}")
        #print(f"    html: {html[start_index:end_index]}")
        data_json = json.loads(html[start_index:end_index])
        dateText = data_json["simpleText"]
        #datetime = parse(dateText)
        return dateText
     
    def _fetch_thumbnail_url(self, html):
        str_target = "\"thumbnails\":"
        start_index, end_index = self._fetch_info_from_html(html, str_target)   
        data_json = json.loads(html[start_index:end_index])
        #print(f"data_json: {data_json}")
        assert isinstance(data_json, list)
        
        # find the thumbnail with max_width
        max_width = 0
        max_idx = 0
        for i, l in enumerate(data_json):
            if max_width < l['width']:
                max_width =  l['width']
                max_idx = i
        thumbnail_url = data_json[max_idx]['url']
        return thumbnail_url
        
    def _fetch_video_by_upload_date(self, date_str):
        from dateutil.parser import parse
        video_upload_datetime = parse(date_str)
        stop_upload_datetime = parse(self.stop_upload_date)
        result = video_upload_datetime >= stop_upload_datetime
        print(f"    video_upload_datetime: {video_upload_datetime.date()}")
        print(f"    after the stop uploaded time: {result}")
        
        return result
        
    ###################################################################################################################################     
    
    def _fetch_video_info(self, video_id, firefox_opts):
    
        """
        Input Arguments:
        1. video_id: 		youtube video id
        3. firefox_opts:	options for firefox browser, normally headless
        
        This will extract video info into a list.
        The video info includes: 
            1. video_title:               str
            2. video_id:                  str
            3. video_upload_date:         datetime object
            4. video_duration:		 str
            5. thumbnail_url:             str, end in ".webp" or ".jpg"
            6. artwork_url:               str or None
            7. chapters:		 dict if video has, contains title,start_time,end_time
            
        Here are some methods to deal with exceptions:
        1. find out the video upload date is before the self.stop_upload_date, then add
           a new key "stop_scrape" into info dict.
        2. 
        """
        info = {} # all video info will be stored in this variable
        
        
        video_url = "https://www.youtube.com/watch?v=" + video_id
            
        
        if self.adblock_add_on_path:
            driver2 = webdriver.Firefox(self.adblock_add_on_path, firefox_options=firefox_opts)
        else:
            driver2 = webdriver.Firefox(firefox_options=firefox_opts)
        
        
        
        self._get_content_from_url(driver2, video_url)
        html = driver2.page_source
        try:    
            # fetch video upload date################################
            info['video_upload_date'] = self._fetch_video_upload_date(html)
            assert isinstance(info['video_upload_date'], str)
            if self.stop_upload_date is not None:
                after_stop_upload_time = self._fetch_video_by_upload_date(info['video_upload_date'])
                if not after_stop_upload_time:
                    driver2.quit()
                    info['stop_scrape'] = True
                    print("    stop_scrape.")
                    #assert 1 == 0
                    return info
                
            video_details_json = self._fetch_video_details(html)
        
            # fetch video title######################################
            video_title = video_details_json['title']
            info['video_title'] = video_title
        
        
            # this is to filer out any shorts videos#################
            # comment this out will download Shorts videos as well
            if "#Shorts" in video_title:
                if "#Shorts" in video_title.split(' ')[-1]:  
                    return 
            # fetch video id#########################################        
            info['video_id'] = video_id
            
            
            duration_seconds = video_details_json['lengthSeconds']
            
            # fetch video chapters####################################
            info['chapters'] = self._fetch_video_chapters(html, duration_seconds)
            
            # usually, video length is less than 6 mins unless it contains chapters.
            if int(duration_seconds) > 10 * 60 and info['chapters'] is None:
                driver2.quit()
                return
            #fetch video duration in seconds###########################    
            info['video_duration'] = duration_seconds
        
            

            # fetch video thumbnail url ###############################   
            info['thumbnail_url'] = self._fetch_thumbnail_url(html)
            # fetch video artwork url    
        
            artwork_link = self._fetch_artwork_link(video_details_json)
            info['artwork_url'] = artwork_link
        
        
            driver2.quit()
        except:
            driver2.quit()
        return info
        
        
        
    def _fetch_video_info_batch(self, driver, saved_path):
        """
        Input Arguments:
            1. driver:				a webdriver object
            2. saved_path:			a directory to contain all videos and channel info files
        Outputs:
            1. channel_videos_id_list.txt	a file contains all video ids, this file exists
                                                 for resuming video info fetch process, which usually takes
                                                 a long time (30 mins or hours), and it's easy to be interrupted
                                                 by broken internet connection.
            2. channel_videos_info_list.json	a file contains all video info, which will be used for video 
                                                 downloader.
                                                 
        Idea:
            Sometimes, fetch all video info and store them into a file could take a long time, which
            is easily interrupted by poor internet connection, and it's a pain to resume the process
            manually. Thus here proposes a solution to automatically start the resume process by checking
            the video numbers recorded in two files: 1."channel_videos_id_list.txt" and 2."channel_videos_info_list.json"
            There are three senarios: 
            	1. both files are created, then check the number of videos (after self.stop_upload_time),
            	       if   the numbers are equal, then no more fetch process
            	       else resume the fetch process from the last video id in video_info_list
            	       
            	2. file 2 not exists but file 1 exists, then resume the fetch process.
            	
            	3. both files are not created, then start the fetch process straightforward.
        """
        
        #print(f"    fetch video info...")
        video_ids_saved_path = os.path.join(saved_path, 'channel_videos_id_list.txt')
        total_info_saved_path = os.path.join(saved_path, 'channel_videos_info_list.json')
        resume_idx = 0
        print(f"    only fetch video which is uploaded after {self.stop_upload_date}.")
        
        
        ##################################################################################################################
        ##################### here are some methods to deal with resume process for video info download###################
        
        
        if os.path.exists(total_info_saved_path) and not self.update:
            print(f"    channel video info has been saved, read video info from {total_info_saved_path}.")
            with open(total_info_saved_path , 'r') as f:
                video_info_list = json.load(f) 
                
            if os.path.exists(video_ids_saved_path):  
                with open(video_ids_saved_path, 'r') as f:
                    video_ids_list = []
                    lines = f.readlines()
                    for line in lines:
                        video_ids_list.append(line.replace('\n', ''))
                    #video_ids_list.reverse()
                # this case means a fetch video info process needs to be resumed  
                start_idx = video_ids_list.index(self.stop_video_id) if self.stop_video_id else 0
                if len(video_info_list) < len(video_ids_list)-start_idx:
                    resume_video_id = video_info_list[-1]['video_id']
                    resume_idx = video_ids_list.index(resume_video_id) + 1
                # this case means all video info has been fetched, just return
                elif  len(video_info_list) == len(video_ids_list) :  
                    driver.quit()
                    return video_info_list
            else:
                driver.quit()
                raise ValueError("please fetch video ids for this channel")
                return
          
        if os.path.exists(video_ids_saved_path) and not self.update:
            if not os.path.exists(total_info_saved_path):
                print(f"    channel video ids have been saved, but no video info json file")
                print(f"    skip channel scroll...")
                video_info_list = []
                with open(video_ids_saved_path, 'r') as f:
                    video_ids_list = []
                    lines = f.readlines()
                    for line in lines:
                        video_ids_list.append(line.replace('\n', ''))
                    # this aims: to append the newest video ids into end of the file
                    #            the scrapered video ids will be reversed in the file.
                    #video_ids_list.reverse()
                    resume_idx = video_ids_list.index(self.stop_video_id) if self.stop_video_id else 0
                 
        else:
            ####this channel has not been fetched before, start to fetch video info process#########################
            self._scroll2bottom_webpage(driver)
            
            video_info_list = []
            
            video_data = driver.find_elements_by_xpath('//*[@id="video-title-link"]')
  
            video_ids_list = []
            
            for v_data in video_data:       
                video_link = v_data.get_attribute('href')
                if video_link is not None:
                    video_id = video_link.split('watch?v=')[-1]
                    video_ids_list.append(video_id)
              
                             
            with open(video_ids_saved_path, 'w') as f:
                f.write('\n'.join(video_ids_list))
            #video_ids_list.reverse()
            resume_idx = video_ids_list.index(self.stop_video_id) if self.stop_video_id else 0
        driver.quit()
        
        print(f"    len(video_ids_list): {len(video_ids_list)}")
        
        
        
        ############start the fetch process###########################################################################
        start_time = time.time()
        for idx in pit(range(resume_idx, len(video_ids_list)), text="fetch video info", color="yellow"):
            
            
            data = video_ids_list[idx].replace('\n','')
            print(f"    resume video_id: {data}")
              
            info = self._fetch_video_info(data, self.opts)
            
            if info is not None and info != {}:         
                if "stop_scrape" in info.keys():
                    # the video_ids are sorted from nearest upload time to farest upload time
                    # thus, the fisrt False of after upload time will stop the scrape process. 
                    print("****Find the first video not after stop upload time, stop the scraping process.******")
                    return video_info_list               
                video_info_list.append(info)
                # write to json file once a new video info is fetched
                with open(total_info_saved_path, 'w', encoding='utf-8') as f:
                    json.dump(video_info_list, f, ensure_ascii=False, indent=4)  
                       
                    
        
            execution_time = time.time() - start_time
            
            # long pause when scraper works over 30 mins
            # otherwise, short pause
            if execution_time / 60 > 30:
                pause_report(length=100, file_count=None,disp=False)
                start_time = time.time()
            else:
                pause_report(length=10,file_count=None,disp=False)
            
        
        
        return video_info_list    
        
        
    def download_youtube_channel(self, channel_url):
        """
        Input Argument:
            channel_url:			youtube channel url
        Outputs:
            1. channel_videos_id_list.txt	a file contains all video ids
            2. channel_videos_info_list.json	a file contains all video info
            3. folders named by video_id	every folder named by a video_id
                                                 which contains videos (mp3 format),
                                                 artwork image (if needed), thumbnail
        """
       
        channel_videos_url = channel_url+'/videos'
       
        
        driver = webdriver.Firefox()
        self._get_content_from_url(driver, channel_videos_url)
        
        # create channel folder#########################################################
        channel_name = channel_url.split('/')[-1]
        channel_id = self._extract_channel_id(driver)
        folder_name = channel_name + '+' + channel_id
        channel_saved_path = os.path.join(self.saved_path, folder_name)
        if not os.path.exists(channel_saved_path):
            os.makedirs(channel_saved_path)
        
        
        
        print("Summary info:=========================================================>")
        print(f"    scrape {channel_url}")
        print(f"    saved_path: \t\t\t{self.saved_path}")
        print(f"    download_file_format: \t\t{self.download_file_format}")
        print(f"    stop_upload_date: \t\t\t{self.stop_upload_date}")
        print(f"    stop_video_id: \t\t\t{self.stop_video_id}")
        print(f"    rename_title: \t\t\t{self.rename_title}")
        print(f"    channel update: \t\t\t{self.update}")
        print("end===================================================================>")
        
        #driver.implicitly_wait(5)
        #time.sleep(5)
        # fetch video info ###############################################################
        video_info_list = self._fetch_video_info_batch(driver, channel_saved_path)
        driver.quit()
        
        
        
        
        # set resume idx by counting the number of folders under channel directory########
        folder_names_list = os.listdir(channel_saved_path)
        if 'channel_videos_id_list.txt' in folder_names_list:
            folder_names_list.remove('channel_videos_id_list.txt')
        if 'channel_videos_info_list.json' in folder_names_list:
            folder_names_list.remove('channel_videos_info_list.json')
        resume_idx = 0
        
        
        print(f"    resume_idx: {resume_idx}")
        
        # start to download videos####################################################################
        start_time = time.time()
        for idx in pit(range(resume_idx,len(video_info_list)), text="download video", color="green"):
            # download video with chapters
            
            if "chapters" not in video_info_list[idx].keys():
                self.download_youtube_video(self.download_file_format, video_info_list[idx], \
                                                channel_saved_path, download_thumbnail=True)
            elif video_info_list[idx]["chapters"] is not None:
                self.download_youtube_video_as_mp3_chapters(self.download_file_format, video_info_list[idx], \
                                                          channel_saved_path, download_thumbnail=True)
            
            execution_time = time.time() - start_time
            
            
            
            # long pause when scraper works over 50 mins
            # otherwise, short pause
            if execution_time / 60 > 50:
                pause_report(length=100, file_count=None,disp=False)
                start_time = time.time()
            else:
                pause_report(length=1,file_count=None,disp=False)
            
