import time
import copy
import re
import emoji
import numpy as np
import os
from difflib import SequenceMatcher

"""
Date: 15 - 30 July 2021
Features:
    1. rename, is able to convert arbitrary audio_filename into expected format:
        artist_usernames - song_name (feat./with/prod. by/cover by artist_usernames) + (artist_usernames remix/mix/flip/cover) + [ncs release]
    2. pit, progress bar
"""
# borrowed from https://stackoverflow.com/questions/23113494/double-progress-bar-in-python
# @Arty
def pit(it, text, *pargs, **nargs):
    import enlighten
    global __pit_man__

    try:
        __pit_man__
    except NameError:
        __pit_man__ = enlighten.get_manager()

    man = __pit_man__

    try:
        it_len = len(it)
    except:
        it_len = None

    try:
        ctr = None
        for i, e in enumerate(it):
            if i == 0:
                ctr = man.counter(*pargs, **{**dict(leave = False, total = it_len, desc= text), **nargs})
            yield e
            ctr.update()
    finally:
        if ctr is not None:
            ctr.close()

# this aims to avoid file system crash when IO is too busy for saving images to disk.
def pause_report(length=10, random_delay=0.25, file_count=1000, disp = True):

    pause_time = length*np.random.normal(1,random_delay)
    if file_count is not None:
        if disp: print(f"    Pausing scraper for {round(pause_time,2)} seconds.")
    else:
        if disp: print(f"    Pausing scraper for {round(pause_time,2)} seconds when one artist scrapering is done.")
    time.sleep(pause_time)

def reformat_url(soundcloud_url):
    url = soundcloud_url.replace(':', '%3A').replace('/', '%2F')
    #print(f"  url: {url}")
    return url

def fetch_track_transcodings(track_info_json):
    if 'media' not in track_info_json.keys():
        #print(f"Error, no media dick key in track_info_json")
        return None
    elif 'transcodings'not in track_info_json['media']:
        #print(f"Error, no transcodings dick key in track_info_json")
        return None
    elif track_info_json['media']['transcodings'] == []:
        #print(f"Error, transcodings is empty in track_info_json")
        #print(f"We cann't download track fragments")
        return None
    #print(f"    fetch_track_transcodings, track_info_json:{track_info_json}")
    formats = []
    for t in track_info_json['media']['transcodings']:
        track_transcoding = {}
        track_transcoding['url'] = t['url']
        track_transcoding['preset'] = t['preset']
        track_transcoding['duration'] = t['duration']
        track_transcoding['format'] = {}
        track_transcoding['format']['protocol'] = t['format']['protocol']
        track_transcoding['format']['mime_type'] = t['format']['mime_type']

        formats.append(track_transcoding)

    return formats

def fetch_track_fragment_format(stream_url):
    mobj = re.search(r'\.(?P<abr>\d+)\.(?P<ext>[0-9a-z]{3,4})(?=[/?])', stream_url)
    return mobj.groupdict()

def sort_formats(formats):
    if not formats:
        raise ExtractorError('No video formats found')

    def _formats_key(f):
        # TODO remove the following workaround
        ORDER = ['webm', 'opus', 'ogg', 'mp3', 'aac', 'm4a']
        try:
            audio_ext_preference = ORDER.index(f['format']['ext'])
        except ValueError:
            audio_ext_preference = -1

        return (
                f['format'].get('abr') if f['format'].get('abr') is not None else -1,
                audio_ext_preference,
            )
    formats.sort(key=_formats_key)
    #print(f"    sort formats: {formats}")

def only_one_parenthesis_in_start_and_end(song_title):
    start_idx = song_title.index('"')
    end_idx = song_title.index('"', start_idx)
    if start_idx == 0 and end_idx == len(song_title) -1:
        return True
    else:
        return False

def remove_delimiter_both_side_of_the_string(string):
    while True:
        if string[0] in [' ', ',', '|']:
            string = string[1:]
        elif string[-1] in [' ', ',', '|']:
            string = string[:-1]
        else:
            break
    return string

def emoji_exist_in_string(str):
    for char in str:
        if char in emoji.UNICODE_EMOJI['en']:
            return True
    return False

def rename(audio_filename, disp=False):
        """
        Input argument:
            audio_filename: don't contain the path, just the name with file format.
        Expected name format:
        {artist_names} - {song_name} (feat xxx)/(with xxx)/(xxx cover)/(cover by xxx)/(xxx remix)/(xxx version)

        This function needs to consider as many cases of arbitrary song title on SoundCloud as possible,
        thus the function is extremely long, so far, it already contains over 600 lines.

        Notice:
        1. The song name better doesn't contain '/' symbol as it will not be saved into directory.
        2. Please find the song name as clean as possible, as the algorithm can not cover all cases.
        3. The song name better doesn't contain the following case: no brackets but with word in unexpected_words_wo_brackets.
           for example, Mokita - Down lyrics.
        """
        if disp:
            print(f"    audio_filename: {audio_filename}")
        #assert 1 == 0
        """------------------------ prepare the audio_filename in certain cases----------------------------"""
        # replace wierd letter ' – '
        if ' – ' in audio_filename:
            audio_filename = audio_filename.replace(' – ', ' - ')

        # sometimes, two spaces '  ' exist in audio_filename.
        # replace it with one space ' '.
        if '  ' in audio_filename:
            audio_filename = audio_filename.replace('  ', ' ')

        # sometimes, there are spaces in the start and end of audio filename,
        # we need to delete them.
        audio_filename = remove_delimiter_both_side_of_the_string(audio_filename)

        #sometimes there are double quote letters "''" in audio_filename
        # we have to convert them to '"'
        audio_filename = audio_filename.replace("''", "'")

        # we assume the left side of ' - ' is artist names
        artist_name = audio_filename.split(' - ')[0]

        # sometimes the brackets is directly next to another word,
        # i.e., Soulmate(ft. Julia Church), we have to seperate them.
        # i.e., Soulmate( ft. Julia Church) -> Soulmate (ft. Julia Church)
        # i.e., Soulmate ( ft. Julia Church) -> Soulmate (ft. Julia Church)
        parts = audio_filename.split(' ')
        parts_modified = copy.deepcopy(parts)
        if disp:
            print(f"    parts_modified before: {parts_modified}")
        for i, part in enumerate(parts):
            for bracket in ['(', '[', '{','|', ')', ']','}']:
                if bracket in part:
                    bracket_idx = part.find(bracket)
                    #print(f"    bracket_idx: {bracket_idx}")
                    if bracket != part:

                        if bracket in ['(', '[', '{', '|']:
                            if bracket_idx != 0 and bracket_idx != len(part)-1:
                                #print(f"    a part: {part}")
                                sub_parts = [part[:bracket_idx], part[bracket_idx:]]
                                removed_index = parts_modified.index(part)
                                parts_modified.remove(part)
                                parts_modified[removed_index:removed_index] = sub_parts
                                break
                            elif bracket_idx == len(part)-1:
                                removed_index = parts_modified.index(part)
                                parts_modified[removed_index] = part[:bracket_idx]
                                parts_modified[removed_index+1] = bracket+parts_modified[i+1]
                                break

                        elif bracket in ['|', ')', ']','}']:
                            if bracket_idx != 0 and bracket_idx != len(part)-1:
                                #print(f"    b part: {part}")
                                sub_parts = [part[:bracket_idx+1], part[bracket_idx+1:]]
                                removed_index = parts_modified.index(part)
                                parts_modified.remove(part)
                                parts_modified[removed_index:removed_index] = sub_parts
                                break
                            elif bracket_idx == 0:
                                removed_index = parts_modified.index(part)
                                parts_modified[removed_index] = part[:bracket_idx]
                                parts_modified[removed_index-1] = parts_modified[i-1]+bracket
                                break
                    else:
                        if bracket in ['(', '[', '{']:
                            #print(f"    aaaaa")
                            removed_index = parts_modified.index(part)
                            parts_modified[removed_index] = ''
                            parts_modified[removed_index+1] = bracket+parts_modified[i+1]
                            #print(f"    i: {i}, removed_index: {removed_index}, parts_modified[removed_index+1]: {parts_modified[removed_index+1]}")
                            break
                        elif bracket in [')', ']','}']:
                            #print(f"    bbbbb")
                            removed_index = parts_modified.index(part)
                            parts_modified[removed_index] = ''
                            parts_modified[removed_index-1] = parts_modified[i-1]+bracket
                            #print(f"    i: {i}, removed_index: {removed_index}, parts_modified[removed_index-1]: {parts_modified[removed_index-1]}")
                            break

        parts_modified = [part for part in parts_modified if part!= '']
        if disp:
            print(f"    parts_modified: {parts_modified}")

        audio_filename = " ".join(parts_modified)
        del parts_modified, parts




        if disp:
            print(f"    audio_filename after preparation: {audio_filename}")
        #assert 1 == 0


        # deal with audio_filename contains multiple ' - '
        # consider the left side of first ' - ' belongs to artist name
        # the right side of first ' - ' belongs to song_name
        song_name = " ".join(audio_filename.split(' - ')[1:])


        # remove quote letters in song_name
        # in the following case, the quote letter will be removed:
        #    1. quote letters only exist in the start and end of songname,
        #       and no other quote letters.
        # But we need to keep the quote letters in the following cases:
        #    1. contraction cases, i.e., Can't, isn't, I've, we're etc
        #    2. special cases, i.e., Fallin'
        def remove_quote_letter(songname):
            # remove all brackets in songname and left true song title
            res_list = extract_string_within_brackets(songname)
            for sub_str in res_list:
                songname = songname.replace(sub_str, '')
            while True:
                if songname[-1] == ' ':
                    songname = songname[:-1]
                elif songname[0] == ' ':
                    songname = songname[1:]
                else:
                    break
            #songname = songname.replace('  ', ' ')
            sym_start_idx = songname.find("\'")
            sym_end_idx = songname.find("\'", sym_start_idx+len("\'"))
            # remove any "\'" that is not part of ["\'ve", "\'s", "\'d", "\'ll", "\'t", "\'m", "\'re"]
            expected_list = []
            for case in ["'ve", "'s", "'d", "'ll", "'t", "'m", "'re", "in'"]:
                expected_list = expected_list + re.findall(f"(\\w+){case}", songname)

            if sym_start_idx == 0 and sym_end_idx == len(songname) - 1 and expected_list == []:
                songname = songname.replace("\'", '')

            # insert bracket string back to original position of songname
            start_idx = 0
            for sub_str in res_list:
                start_idx = songname.find('  ', start_idx)
                if start_idx == -1:
                    songname += ' ' + sub_str
                else:
                    songname = songname[:start_idx+1] + sub_str + songname[start_idx+1:]
                    start_idx += len('  ')

            return songname

        song_name = remove_quote_letter(song_name)
        if disp:
           print(f"    song_name: {song_name}")
        #assert 1 == 0


        #print(f"    song_name: {song_name}")
        # in expected_words_in_brackets, first line, i.e.,'feat', 'ft', 'with' is prefix, the others are suffix
        expected_words_in_brackets = ['feat', 'ft', 'with','produced by', 'prod by', 'prod. by', 'prod', 'cover by', 'remix by',
                                      'cover', 'remix', 'mix','version','ver','edition','edit', 'ncs release', 'flip']
        # in unexpected_words_wo_brackets, all of them are prefix,
        # one interesting word: dance
        unexpected_words_wo_brackets = ['official', 'official remix', 'lyric', 'ultra',
                                        'edm music', 'dance music', 'pop music', #'music',
                                        'video', 'audio', 'record', 'vocal',
                                        'free download', 'free dl', 'download', 'bbc',
                                        'radio', 'acoustic', 'original','demo', '@',
                                        'out now', 'vip', 'premiere', 'Bootleg', 'buy now']

        """--------------------------end of preparation for audio_filename------------------------------"""


        """--------------------process the artist names and song_name-----------------------------------"""
        # process artist name
        # notice: we only consider the artist name behind words in expected_words_in_brackets
        # remove artist name from left side of first ' - ' to right side.
        # for example, Allix X R3HAB (feat. Jamie) - Fallin' Down
        #           --> Allix X R3HAB - Fallin' Down (feat. Jamie)
        artist_name_start_idx = 0
        for word in ['feat', 'ft', 'with', 'prod', 'produced', 'ncs']: # 'ncs' denotes ncs release
            if disp:
                print(f"    word: {word} and artist_name: {artist_name}")
            res = re.findall(f"\\b{word}\\b", artist_name.lower())
            if res != []:
                artist_name_start_idx = artist_name.lower().find(word)
                split_parts = re.split('(\W+)',artist_name.lower())
                idx = split_parts.index(word)
                sub_str_to_be_found = "".join(split_parts[idx-1:])
                #print(f"    ")
                artist_name_start_idx = artist_name.lower().find(sub_str_to_be_found)
                break
        # check if parenthesis exist in artist_username
        # if parenthesis exists, it will be moved to the right side of " - "
        if artist_name_start_idx == 0:
            string_within_brackets = extract_string_within_brackets(artist_name.lower())
            if string_within_brackets != []:
                artist_name_start_idx = artist_name.lower().find(string_within_brackets[0])


        if disp:
            print(f"        artist_name_start_idx: {artist_name_start_idx}")
        if artist_name_start_idx != 0:
            moved_part = artist_name[artist_name_start_idx:]
            artist_name = artist_name[:artist_name_start_idx]
        else:
            moved_part = ''

        artist_name = remove_delimiter_both_side_of_the_string(artist_name)

        ####print(f"    artist_name: {artist_name}")
        if disp:
            print(f"    moved_part: {moved_part}")

        # move the moved_part back to song_name
        if moved_part != '':
            if song_name.find('(') != -1:
                insert_idx = song_name.find('(')
            elif song_name.find('[') != -1:
                insert_idx = song_name.find('[')
            elif song_name.find('{') != -1:
                insert_idx = song_name.find('{')
            else:
                insert_idx = -1

            if insert_idx == -1:
                #print('dddddd')
                song_name += ' ' + moved_part if moved_part[0] != ' ' else moved_part
            else:
                #print('eeeee')
                #insert_idx -= 1

                song_name = song_name[:insert_idx] + moved_part +' ' + song_name[insert_idx:]

        if disp:
            print(f"    song_name after moved: {song_name}")
        #assert 1== 0
        ##########################################################################################

        def check_left_right_side(string_within_bracket, song_name, check_start_idx, start_idx):
            left_side = song_name.find(string_within_bracket) - 1
            right_side = song_name.find(string_within_bracket) + len(string_within_bracket)
            #print(f"    left_side: {left_side} and right_side: {right_side}")
            #print(f"    song_name: {song_name}, len(song_name):{len(song_name)}")
            #assert 1 == 0
            if left_side >= 0 and right_side < len(song_name):
                #print(f"    aaaaaa")
                check_start_idx += start_idx
                return 'remove space in left_side', check_start_idx
            elif left_side == -1 and right_side < len(song_name):
                #print(f"    bbbbbbbb")
                check_start_idx = 0
                return 'remove space in right_side', check_start_idx
            elif left_side >= 0 and right_side == len(song_name):
                #print(f"    ccccccc")
                check_start_idx = start_idx - 1
                return 'remove space in left_side', check_start_idx
            elif left_side == -1 and right_side == len(song_name):
                raise ValueError(f"    Error, song_name: {song_name} only contains string within brackets.")
                return

        def determine_preserve_or_not(uncertain_part, preserved, check_start_idx,
                                      song_name, left_bracket='(', right_bracket=')'):
            #if left_bracket in uncertain_part and right_bracket in uncertain_part:
                if disp:
                    print(f"    left_bracket: {left_bracket}, right_bracket: {right_bracket}")

                start_idx = uncertain_part.find(left_bracket)
                end_idx = uncertain_part.find(right_bracket, start_idx)
                found_unexpected = False
                string_within_bracket =  uncertain_part[start_idx:end_idx+1].lower()
                if disp:
                    print(f"    string_within_bracket: {string_within_bracket}")
                for word in unexpected_words_wo_brackets:
                    if word in string_within_bracket:
                        if disp:
                            print(f"    unexpected_words_wo_brackets word: {word}")
                        res = re.findall(f"\\b{word}\\b", string_within_bracket)
                        if res != []:
                            found_unexpected = True
                            break
                if not found_unexpected:
                    for word in expected_words_in_brackets:
                        if disp:
                            print(f"    expected_words_in_brackets word: {word}")
                        if word in string_within_bracket:
                            res = re.findall(f"\\b{word}\\b", string_within_bracket)
                            #print(f"    res: {res}")
                            if res != []:
                                check_start_idx += end_idx + 1
                                preserved = True
                                break
                if disp:
                    print(f"    determine_preserve_or_not, preserved: {preserved}")
                if not preserved:
                    # usually, the remove "(words)" could cause double space letters
                    # thus, we check if it does, if yes, remove one of space letters
                    # otherwise, we do nothing
                    #print(f"    song_name[check_start_idx+end_idx+1]: {song_name[check_start_idx+end_idx+1]}")
                    #print(f"    song_name[check_start_idx+end_idx+1+1]: {song_name[check_start_idx+end_idx+1+1]}")

                    #print(f"    a   aaaaaa")
                    side_remove_space, check_start_idx = check_left_right_side(uncertain_part[start_idx:end_idx+1],
                                                         song_name, check_start_idx, start_idx)
                    if side_remove_space == 'remove space in left_side':
                        #print(f"    leftside before song_name:{song_name}, len(song_name):{len(song_name)}, check_start_idx: {check_start_idx}")
                        song_name = song_name.replace(' '+uncertain_part[start_idx:end_idx+1], '')
                        #print(f"    leftside after song_name:{song_name}, len(song_name):{len(song_name)}, check_start_idx: {check_start_idx}")
                    elif side_remove_space == 'remove space in right_side':
                        #print(f"    rightside before song_name:{song_name}, len(song_name):{len(song_name)}, check_start_idx: {check_start_idx}")
                        song_name = song_name.replace(uncertain_part[start_idx:end_idx+1]+' ', '')
                        #print(f"    rightside after song_name:{song_name}, len(song_name):{len(song_name)}, check_start_idx: {check_start_idx}")
                    #check_start_idx += start_idx

                #print(f"    check_start_idx: {check_start_idx}")
                return preserved, check_start_idx, song_name




        def deal_without_brackets(uncertain_part, preserved, check_start_idx):
            if disp:
                print(f"    deal without brackets")
            for word in expected_words_in_brackets:
                if word in uncertain_part.lower():

                    res = re.finditer(f"\\b{word}\\b", uncertain_part.lower())
                    start_indices = [m.start() for m in res]
                    if start_indices != []:
                        start_idx = start_indices[0]
                        if disp:
                            print(f"    expected word in brackets: {word}")
                    else:
                         continue
                    # prefix words
                    if word in ['feat', 'with', 'ft', 'produced by', 'prod. by', 'prod by', 'prod',  'cover by', 'remix by',]:
                        #print(f"    a a a word: {word}")
                        stop_criteria_symbols = ['(', '[',  '{','|']
                        stop_criteria_words = unexpected_words_wo_brackets

                        for criteria in stop_criteria_symbols + stop_criteria_words:
                            if criteria in stop_criteria_symbols:
                                found_criteria_idx = uncertain_part.lower().find(criteria, start_idx+len(word))
                            else:
                                #print(f"    criteria word: {criteria}")
                                res = re.finditer(f"\\b{criteria}\\b", uncertain_part.lower())
                                indices = [m.start() for m in res]
                                #print(f"    indices: {indices}")
                                if indices ==[]:
                                    continue
                                # find the first idx larger than start_idx+len(keyword)
                                for idx in indices:
                                    if idx > start_idx+len(word):
                                        found_criteria_idx = idx  #string_to_be_checked.find(criteria, start_idx+len(keyword))
                                        break
                            #print(f"    found_criteria_idx: {found_criteria_idx}")
                            if found_criteria_idx > 0:
                                if uncertain_part.lower()[found_criteria_idx-1] == ' ':
                                    found_criteria_idx -= 1
                                break
                        if found_criteria_idx > 0:
                            check_start_idx += found_criteria_idx
                        else:
                            check_start_idx += len(uncertain_part.lower())
                        #print(f"    check_start_idx: {check_start_idx}, found_criteria_idx:{found_criteria_idx}")

                    # suffix words
                    elif word in ['cover', 'remix', 'mix','version','ver', 'edition','edit', 'ncs release', 'flip' ]:

                        if start_idx != len(uncertain_part) - 1:
                            if uncertain_part.lower()[start_idx + 1] in [')', ']', '}']:
                                check_start_idx += start_idx + len(word) + 1
                            else:
                                check_start_idx += start_idx + len(word)
                        else:
                            check_start_idx += start_idx + len(word)
                    #assert 1 == 0

                    #print(f"    check_start_idx after: {check_start_idx}, uncertain_part[start_idx+len(word):]: {uncertain_part[start_idx+len(word):]}")
                    preserved = True
                    break

            return preserved,check_start_idx
        # process song name
        check_start_idx = 0

        while True:
            if disp:
                print(f"    song_name: {song_name}")
            previous_check_start_idx = check_start_idx

            preserved_part = song_name[:check_start_idx]
            uncertain_part = song_name[check_start_idx:]
            if disp:
                print(f"    preserved_part: {preserved_part}")
                print(f"    uncertain_part: {uncertain_part}")
            #remove all unexpected brackets
            preserved = False

            if '(' in uncertain_part and ')' in uncertain_part:
                preserved,check_start_idx, song_name = determine_preserve_or_not( uncertain_part, preserved,
                                                       check_start_idx,song_name,'(', ')')
            elif '[' in uncertain_part and ']' in uncertain_part:
                preserved,check_start_idx, song_name = determine_preserve_or_not( uncertain_part, preserved,
                                                       check_start_idx,song_name,'[', ']')
            elif '{' in uncertain_part and '}' in uncertain_part:
                preserved,check_start_idx, song_name = determine_preserve_or_not( uncertain_part, preserved,
                                                       check_start_idx,song_name,'{', '}')
            else:
                preserved,check_start_idx = deal_without_brackets(uncertain_part, preserved, check_start_idx)

            if disp:
                print(f"    perserved: {preserved}, song_name[check_start_idx:]: {song_name[check_start_idx:]}")
            # in the determine_preserve_or_not, we could change the song_name
            # thus, the uncertain_part should be new song_name[previous_check_start_idx:] as well
            #print(f"    uncertain_part: {uncertain_part}, song_name[previous_check_start_idx:]: {song_name[previous_check_start_idx:]}")
            if uncertain_part != song_name[previous_check_start_idx:]:
                #uncertain_part = song_name[previous_check_start_idx:]
                continue

            # remove unexpected words when no parenthesis existing in uncertain_part
            if not preserved:
                found_unexpected = False
                for word in unexpected_words_wo_brackets:
                    #print(f"    word: {word}")
                    if word in uncertain_part.lower():
                        if word == "@":
                            #print(f"    aaaaaa")
                            check_start_idx += uncertain_part.find(word)
                            found_unexpected = True
                            break
                        # f"\W*{word}\W*" will not find the exact word
                        res = re.finditer(f"\\b{word}\\b", uncertain_part.lower())
                        indices = [m.start() for m in res]
                        #print(f"    indices: {indices}")
                        if indices != []:
                            if disp:
                                print(f"    found unexpected word: {word}")
                            if indices[0] > 0:
                                #print(f"    uncertain_part[indices[0]-1]: {uncertain_part[indices[0]-1]}")
                                if  uncertain_part[indices[0]-1] in ['-', '_', '*', '^',
                                                                     '#', '@', ':',';',
                                                                     ',','.']:
                                    check_start_idx += indices[0] - 1
                                else:
                                    check_start_idx += indices[0]
                            found_unexpected = True
                            break
                        else:
                            continue

                if disp:
                    print(f"    found_unexpected: {found_unexpected}")
                    print(f"    not preserved preserved: {preserved}")
                    print(f"    check_start_idx: {check_start_idx}")
                # in this case, the song name is already clear to go, thus
                # just exit the while loop
                if not found_unexpected:
                    #print(f"    check_start_idx before: {check_start_idx}, song_name: {song_name}, len(song_name): {len(song_name)}")
                    if check_start_idx != len(song_name) :
                        check_start_idx += len(uncertain_part)
                        preserved = True
                    elif preserved_part == '':
                        if check_start_idx>0 and check_start_idx <= len(song_name):
                            preserved = True
                else:
                    if preserved_part == '':
                        if check_start_idx>0 and check_start_idx <= len(song_name):
                            preserved = True

                    #print(f"    check_start_idx after: {check_start_idx}")
            if disp:
                print(f"    after not preserved preserved: {preserved}, check_start_idx: {check_start_idx}")
            #assert 1 == 0
            if not preserved:
                break
        if disp:
            print(f"    preserved_part: {preserved_part}")
        #assert 1 == 0



        # remove all left spaces in the tail of string.
        preserved_part = remove_delimiter_both_side_of_the_string(preserved_part)




        ########################################################################################

        def add_brackets_into_string(keyword, preserved_part):
            res = re.finditer(f"\\b{keyword}\\b", preserved_part.lower())
            start_indices = [m.start() for m in res]
            #print(f"    preserved_part: {preserved_part}")
            string_to_be_checked = preserved_part.lower()
            for start_idx in start_indices:

                #print(f"    string_to_be_checked: {string_to_be_checked}")
                add_bracket_or_not = False
                found_bracket = False

                string_within_brackets = extract_string_within_brackets(string_to_be_checked)
                for str in string_within_brackets:
                    #print(f"    str: {str}, start_idx:{start_idx}")
                    sta_idx = string_to_be_checked.find(str)
                    end_idx = sta_idx + len(str)
                    #print(f"    sta_idx:{sta_idx}, end_idx: {end_idx}")
                    if start_idx > sta_idx and start_idx < end_idx:
                        found_bracket = True
                        break

                if not found_bracket:
                    ###########this isn't right, we still need to add 'ft.', 'feat.'
                    stop_criteria_symbols = ['(', '[', '|', '{','\'']
                    stop_criteria_words = ['ft', 'feat', 'with', 'cover by', 'prod', 'produced']
                    found_stop = False
                    #str_after_keyword = string_to_be_checked[start_idx+len(keyword):]

                    for criteria in stop_criteria_symbols + stop_criteria_words:
                        #sub_str_to_be_checked = string_to_be_checked[start_idx+len(keyword):]
                        if criteria in stop_criteria_symbols:
                            found_criteria_idx = string_to_be_checked.find(criteria, start_idx+len(keyword))
                        else:
                            res = re.finditer(f"\\b{criteria}\\b", string_to_be_checked)
                            indices = [m.start() for m in res]
                            if indices ==[]:
                                continue
                            # find the first idx larger than start_idx+len(keyword)
                            for idx in indices:
                                if idx > start_idx+len(keyword):
                                    found_criteria_idx = idx  #string_to_be_checked.find(criteria, start_idx+len(keyword))
                                    break
                        if found_criteria_idx > 0:
                            if string_to_be_checked[found_criteria_idx-1] == ' ':
                                end_idx = found_criteria_idx - 1
                            else:
                                end_idx = found_criteria_idx
                            found_stop = True
                            break

                    if found_stop:
                        preserved_part = preserved_part[:end_idx] + ')' + preserved_part[end_idx:]
                    else:
                        preserved_part = preserved_part + ')'

                    preserved_part = preserved_part[:start_idx] + '(' + preserved_part[start_idx:]

            return preserved_part

        #
        # convert any other unexpected format to desired one by adding ()
        if 'ft.' in preserved_part.lower() or ' ft ' in preserved_part.lower() or \
            '(ft ' in preserved_part.lower():


            preserved_part = add_brackets_into_string('ft', preserved_part)

            # replace
            if 'ft.' in preserved_part:
                preserved_part = preserved_part.replace('ft.', 'feat.')
            elif 'Ft.' in preserved_part:
                preserved_part = preserved_part.replace('Ft.', 'feat.')
            elif 'FT.' in preserved_part:
                preserved_part = preserved_part.replace('FT.', 'feat.')
            elif '(ft ' in preserved_part:
                preserved_part = preserved_part.replace('(ft ', '(feat. ')
            elif 'Ft' in preserved_part:
                res = re.finditer("\\bFt\\b", preserved_part)
                start_indices = [m.start() for m in res]
                for start_idx in start_indices:
                    preserved_part = preserved_part[:start_idx] +'feat.' + \
                                     preserved_part[start_idx+len('Ft'):]
            elif 'FT' in preserved_part:
                res = re.finditer("\\bFT\\b", preserved_part)
                start_indices = [m.start() for m in res]
                for start_idx in start_indices:
                    preserved_part = preserved_part[:start_idx] +'feat.' + \
                                     preserved_part[start_idx+len('FT'):]

        elif 'feat' in preserved_part.lower():

            preserved_part = add_brackets_into_string('feat', preserved_part)

            if 'feat' in preserved_part and 'feat.' not in preserved_part:
                res = re.finditer("\\bfeat\\b", preserved_part)
                start_indices = [m.start() for m in res]
                for start_idx in start_indices:
                    preserved_part = preserved_part[:start_idx] +'feat.' + \
                                     preserved_part[start_idx+len('feat'):]

            elif 'Feat' in preserved_part and 'Feat.' not in preserved_part:
                res = re.finditer("\\bFeat\\b", preserved_part)
                start_indices = [m.start() for m in res]
                for start_idx in start_indices:
                    preserved_part = preserved_part[:start_idx] +'feat.' + \
                                     preserved_part[start_idx+len('Feat'):]
            elif 'Feat.' in preserved_part:
                res = re.findall("\\bFeat.\\b", preserved_part)
                if res!= []:
                    preserved_part = preserved_part.replace('Feat.', 'feat.')

        if disp:
            print(f"    preserved_part after ft/feat: {preserved_part}")

        if 'cover by' in preserved_part.lower():

            preserved_part = add_brackets_into_string('cover by', preserved_part)

        if "(cover) by" in preserved_part.lower():
            begin_idx = preserved_part.lower().find("(cover) by")
            end_idx = begin_idx + len("(cover) by")
            preserved_part = preserved_part[:begin_idx] + "cover by" + preserved_part[end_idx:]
            preserved_part = add_brackets_into_string('cover by', preserved_part)

        if "(remix) by" in preserved_part.lower():
            begin_idx = preserved_part.lower().find("(remix) by")
            end_idx = begin_idx + len("(remix) by")
            preserved_part = preserved_part[:begin_idx] + "remix by" + preserved_part[end_idx:]
            preserved_part = add_brackets_into_string('remix by', preserved_part)

        if 'with' in preserved_part.lower():

            # sometimes, 'with' could be just part of name, for example, 'Better with you'
            # to deal with such cases, we don't consider cases that 'with' is followed by
            # 'you', 'me', 'him', 'her'
            # but we have to exclude the cases that 'with' is part of another word, i.e.,
            # 'without', 'within'
            special_cases = ['you', 'me', 'him', 'her', '(', '[', '{','us', 'them', 'u', 'it']
            start_idx = preserved_part.lower().find('with')

            # this bool variable determine if the 'with' will title or not
            # here we consider 2 cases:
            #    1. 'with' is contained in one word, like 'without'
            #    2. 'with' followed by special words,like 'you', 'me'
            with_title_or_not = False

            res = re.findall(f"(\w*)with(\w*)", preserved_part.lower())

            for idx, case in enumerate(res):

                if case[0] != '' or case[1] != '':
                    with_title_or_not = True
                    break
                # as '(' will not be selected by (\w*)
                # thus only both be '' that it means ' with '
                elif case[0] == '' and case[1] == '':
                    if preserved_part.lower().split('with')[idx+1].split(' ')[1] in special_cases:
                        with_title_or_not = True
                    else:
                        # here we will add brackets to cover
                        # check left bracket exists or not
                        string_to_be_checked = preserved_part.lower().split('with')[idx]
                        if disp:
                            print(f"    string_to_be_checked: {string_to_be_checked}")
                        found_bracket = False
                        for bracket in ['(', '[', '{']:
                            if bracket in string_to_be_checked:
                                found_bracket = True
                                break
                        if not found_bracket:
                            #print(f"    bracket: {bracket}")
                            start_idx = preserved_part.lower().index(string_to_be_checked) + \
                                            len(string_to_be_checked)
                            stop_criteria = ['(', '[', ',', '{','|']
                            found_stop = False
                            for idx in range(start_idx, len(preserved_part)):
                                if preserved_part[idx] in stop_criteria:
                                    end_idx = idx - 1 if preserved_part[idx] != ',' else idx
                                    found_stop = True
                                    break
                            if found_stop:
                                preserved_part = preserved_part[:end_idx] + ')' + preserved_part[end_idx:]
                            else:
                                preserved_part = preserved_part + ')'

                            preserved_part = preserved_part[:start_idx] + '(' + preserved_part[start_idx:]

        if 'prod' in preserved_part.lower():
            preserved_part = add_brackets_into_string('prod', preserved_part)

        if 'produced' in preserved_part.lower():
            preserved_part = add_brackets_into_string('produced', preserved_part)

        if 'acoustic' in preserved_part.lower():
            preserved_part = add_brackets_into_string('acoustic', preserved_part)

        if disp:
            print(f"    preserved_part after: {preserved_part}")


        # get the final filename, here song_name is in all lower case.
        song_name = preserved_part
        #print(f"    song_name: {song_name}")
        filename = artist_name + ' - ' + title(song_name, disp)
        #print(f"    filename titled: {filename}")

        #########################################################################################
        # lower cases need to be considered
        # the following words should be in lower cases in the audio_filename
        for word in ['with', 'cover by', 'remix by', 'feat.',
                     'prod. by', 'produced by','prod by', 'of', 'and']:
            #print(f"{word.capitalize()}")
            if word.title() in filename:
                filename = filename.replace(word.title(), word)
                # here consider that if the followed word of 'with' is special
                # cases like you, me or him, then we should capitalize word 'with'
                # as it is part of song title.
                #"""
                if word == 'of':
                    res = re.finditer("\\bof\S+", filename)
                    start_indices = [m.start() for m in res]
                    for start_idx in start_indices:
                        filename = filename[:start_idx] + filename[start_idx].capitalize() +\
                                   filename[start_idx+1:]

                if word == 'with':
                    if with_title_or_not:
                        filename = filename.replace(word, word.capitalize())
                if word == 'and':#########################################
                    res = re.finditer("\\band\\b", filename)
                    start_indices = [r.start() for r in res]
                    #print(f"    start_indices: {start_indices}")
                    if start_indices == []:
                        filename = filename.replace(word, word.title())
                        break

                    string_within_brackets = extract_string_within_brackets(filename.lower())
                    for start_idx in start_indices:
                        #print("aaaaaaaa")
                        for s in string_within_brackets:
                            #print("bbbbbbbbbb")
                            bracket_start_idx = filename.lower().find(s)
                            bracket_end_idx = bracket_start_idx + len(s)
                            followed_word = filename[start_idx+len(word)]
                            if followed_word == ' ':
                                if start_idx >= bracket_start_idx and start_idx + len(word) <= bracket_end_idx:
                                    #print(f"    xxxxxxxx")
                                    filename = filename.replace(word.title(), word)
                                    break

        # remove all duplicate strings within any kind of bracket
        filename = remove_duplicate_brackets(filename)

        #print(f"  filename: {filename}")
        #assert 1 == 0
        return filename

def determine_parenthesis_closed_or_not(string):
    found_brackets = []
    expected_left_brackets = ['(', '[', '{']
    expected_right_brackets = [')',']','}']

    for idx, s in enumerate(string):
        if s in expected_left_brackets:
            found_brackets.append((s,idx))
        elif s in expected_right_brackets:
            if found_brackets != []:
                (bracket, i) = found_brackets.pop()
                if bracket == '(' and s != ')':
                    print(f"    The filename contains sring: {string} with unpaired parenthesis: {s}")
                    return False
                elif bracket == '[' and s != ']':
                    print(f"    The filename contains sring: {string} with unpaired parenthesis: {s}")
                    return False
                elif bracket == '{' and s != '}':
                    print(f"    The filename contains sring: {string} with unpaired parenthesis: {s}")
                    return False
            else:
                print(f"    The filename contains sring: {string} with unclosed parenthesis: {s}")
                return False
    if found_brackets != []:
        print(f"    The filename contains sring: {string} with unclosed parenthesis")
        return False
    else:
        return True

def extract_string_within_brackets(string):
    results = []
    found_brackets = []
    expected_left_brackets = ['(', '[', '{']
    expected_right_brackets = [')',']','}']

    for idx, s in enumerate(string):
        if s in expected_left_brackets:
            found_brackets.append((s,idx))
        elif s in expected_right_brackets:
            """
            if found_brackets != []:
                (s, i) = found_brackets.pop()
            else:
                print(f"    The filename contains sring: {string} with unclosed parentness: {s}")
                return
            if found_brackets == []:
                results.append(string[i: idx+1])
            """
            if found_brackets != []:
                (bracket, i) = found_brackets.pop()
                if bracket == '(' and s != ')':
                    print(f"    The filename contains sring: {string} with unpaired parenthesis: {s}")
                    return
                elif bracket == '[' and s != ']':
                    print(f"    The filename contains sring: {string} with unpaired parenthesis: {s}")
                    return
                elif bracket == '{' and s != '}':
                    print(f"    The filename contains sring: {string} with unpaired parenthesis: {s}")
                    return
            if found_brackets == []:
                results.append(string[i: idx+1])
    #print(f"    extracted substrings within brackets: {results}")
    return results

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def remove_duplicate_brackets(filename):

    #res = re.findall(r"\(.*?\)|\[.*?\]|\{.*?\}", filename)
    res = extract_string_within_brackets(filename)
    #print(f"    res duplicate: {res}")
    deleted_elements = set()
    for idx_former in range(0,len(res)-1):
        for idx_latter in range(idx_former+1, len(res)):
            if similar(res[idx_former], res[idx_latter]) > 0.8:
                #print("xxxx")
                deleted_elements.add(res[idx_latter])
    for del_element in deleted_elements:
        idx = filename.find(del_element)
        if idx!=0 and filename[idx-1] == ' ':
            filename = filename.replace(' '+del_element, '')
        else:
            filename = filename.replace(del_element, '')

    return filename

def artist_name_or_not(part,name):

    # find all indices for part in name
    # can't use re.finditer as part could contain unparenthesis,like "iE-z)"
    start_indices = []
    idx = 0
    while True:
        idx = name.find(part, idx)
        if idx != -1:
            start_indices.append(idx)
            idx += len(part)
        else:
            break

    string_within_brackets = extract_string_within_brackets(name)
    for start_index in start_indices:
        for s in string_within_brackets:
            bracket_start_idx = name.find(s)
            bracket_end_idx = bracket_start_idx + len(s)
            if start_index >= bracket_start_idx and start_index + len(part) <= bracket_end_idx:
                return True

    return False

# this aims to deal with song name contains a word
# in which the letters are all upper case
def title(name,disp):


        parts = name.split(' ')
        if '' in parts:
            raise ValueError(f"    name: contain multiple space connected, parts: {parts}")
            return
        if disp:
            print(f"    title name: {name}, parts:{parts}")
        #assert 1 == 0

        # sometimes, the songname could contain  something like
        # "NAME's" in which the 'NAME' is all in upper case.
        # to deal with such case, we need to further split word into parts,
        # then insert splited parts back to parts.
        # BUT we need to remove the case "in'", e.g., Ballin', Dreamin', Lookin'
        parts_modified = copy.deepcopy(parts)
        # contraction cases that are common in english language
        special_cases = ["\'ve", "\'s", "\'d", "\'ll", "\'t", "\'m", '\'re']
        for idx, part in enumerate(parts):
            #print(f"    idx: {idx}, part: {parts}")

            if '\'' in part and 'in\'' not in part:
                special_cases_or_not = False
                for case in special_cases:
                    if case in part.lower():
                        special_cases_or_not = True
                        break
                #print(f"    \' exists in song_name.")
                index = part.find('\'')
                #print(f"    index: {index}")
                #assert 1 == 0
                if index == 0 or index == len(part)-1 or special_cases_or_not:
                    sub_parts = [part]
                else:
                    sub_parts = [part[:index], part[index:]]

                #print(f"    sub_parts:{sub_parts}")
                del parts_modified[idx]

                for insert_index in range(idx, idx+len(sub_parts)):
                    parts_modified.insert(insert_index, sub_parts[insert_index - idx])
            # sometimes, the songname could contain '-' and the followed
            # word is capitalized, for example, "T-Shirts" or "Anti-Everything".
            # to deal with such cases, we will further split word into parts,
            # then insert splitted parts back to parts.

            if '-' in part:
                index = part.find('-')

                if index != len(part)-1:
                    if not artist_name_or_not(part, name):
                        sub_parts = [part[:index], part[index:]]
                    else:
                        sub_parts = [part]
                else:
                    sub_parts = [part[:index], part[index]]

                del parts_modified[idx]
                for insert_index in range(idx, idx+len(sub_parts)):
                    parts_modified.insert(insert_index, sub_parts[insert_index - idx])
        if disp:
            print(f"    parts_modified: {parts_modified}")
        #assert 1 == 0
        parts = copy.deepcopy(parts_modified)
        del parts_modified


        # this is deal with special word like 'iSOAP' or 'mRNA'
        def check_special_word(word):
            if word[0] not in ['(', '[', '|', '\"', '“', '-']:
                string_to_be_checked = word
            else:
                string_to_be_checked = word[1:]

            if string_to_be_checked == string_to_be_checked.capitalize() or \
                string_to_be_checked == string_to_be_checked.lower():
                return False
            else:
                return True

        result = ''
        for idx in range(0, len(parts)):
            if disp:
                print(f"    parts[idx]: {parts[idx]}, len: {len(parts[idx])}")
            if idx != len(parts) -1:

                if check_special_word(parts[idx]):
                    result += parts[idx] + ' '
                    continue

                # this is to aviod the case when the first letter of parts[idx]
                # is '(', '[' or '|', otherwise, the rightful first letter of parts[idx]
                # will not be capitalized.
                #print(f"    idx: {idx}")
                if parts[idx][0] not in ['(', '[', '{', '|', '\"', '“', '-']:
                    if not parts[idx].isupper():
                        #print('   aaaa')
                        found_special_char = False
                        for special_char in ['(', '[', '{', '|', '\"', '“', '-']:
                            start_idx = parts[idx].find(special_char)
                            #print(f"    start_idx: {start_idx}, parts[idx]:{parts[idx]}")
                            if start_idx == -1 :
                                continue
                            if start_idx != len(parts[idx]) -  1:
                                #print('ccccc')
                                found_special_char = True
                                parts[idx] = parts[idx][:start_idx+1] + parts[idx][start_idx+1:].capitalize() + ' '
                                result += parts[idx]
                                break
                            else:
                                #print('sssss')
                                found_special_char = True
                                result += parts[idx].capitalize() + ' '
                                break

                        if not found_special_char:
                            result += parts[idx].capitalize() + ' '
                    else:
                        #print('    xxxxx')
                        result += parts[idx] + ' '
                        #print(f"    result: {result}, len result: {len(result)}")
                else:
                    if not parts[idx][1:].isupper():
                        #print('bbbbb')
                        result += parts[idx][0] + parts[idx][1:].capitalize() + ' '
                    else:
                        result += parts[idx] + ' '


            else:
                if disp:
                    print(f'    parts[idx]: {parts[idx]}')

                if check_special_word(parts[idx]):
                    result += parts[idx]
                    continue

                if parts[idx][0] not in ['(', '[', '{', '|', '\"', '“', '-']:
                    if not parts[idx].isupper():
                        #print('    ccccc')
                        result += parts[idx].capitalize()
                    else:
                        #print('    ddddd')
                        result += parts[idx]
                else:
                    if not parts[idx][1:].isupper():
                        #print('    eeeee')
                        result += parts[idx][0] + parts[idx][1:].capitalize()
                        #print(f"    result: {result}, len result: {len(result)}")
                    else:
                        #print('    aaaaa')
                        result += parts[idx]


            #print(f"    result before special_cases: {result}, len: {len(result)}")
            if parts[idx] in special_cases:
                split_result = result[:-(len(parts[idx])+1)]
                #print(f"    split_result: {split_result}")
                if split_result[-1] == ' ':
                    result = split_result[:-1] + parts[idx] + ' '
            #print(f"    result after special_cases: {result}, len: {len(result)}")

            #print(f"    parts[idx]: {parts[idx]}, parts[idx] len:{len(parts[idx])}")
            if parts[idx][0] == '-':
                if result[-1] in [' ', ')',']', '}', '\"', '”']:
                    split_result = result[:-(len(parts[idx])+1)]
                else:
                    split_result = result[:-(len(parts[idx]))]
                #print(f"    split_result: {split_result}, len: {len(split_result)}, split_result[-1]: {split_result[-1]}")
                if split_result[-1] == ' ':
                    if idx!= len(parts) - 1:
                        result = split_result[:-1] + parts[idx] + ' '
                    else:
                        result = split_result[:-1] + parts[idx]
            #print(f"    result after: {result}, len: {len(result)}")

        #print(f"    title result: {result}")
        #assert 1 == 0
        return result
