'''
**********************************************************
*@license GNU General Public License, version 3 (GPL-3.0)*
**********************************************************
'''

import re
import os
import sys
import json
import html
from urllib.parse import urlencode, quote, unquote, parse_qsl, quote_plus, urlparse, urlunparse
from datetime import datetime, timedelta, timezone
import time
import requests
import xbmc
import xbmcvfs
import xbmcgui
import xbmcplugin
import xbmcaddon
import base64
import traceback

addon_url = sys.argv[0]
addon_handle = int(sys.argv[1])
params = dict(parse_qsl(sys.argv[2][1:]))
addon = xbmcaddon.Addon(id='plugin.video.newddhd')

mode = addon.getSetting('mode')
baseurl = addon.getSetting('baseurl').strip()
schedule_path = addon.getSetting('schedule_path').strip()
schedule_url = baseurl + schedule_path
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
FANART = addon.getAddonInfo('fanart')
ICON = addon.getAddonInfo('icon')
# Cache for schedule and live tv
schedule_cache = None
cache_timestamp = 0
livetv_cache = None
livetv_cache_timestamp = 0
cache_duration = 900  # 15 minutes = 900 seconds

AUTH_SERVER = "https://top2new.newkso.ru"
CDN1_BASE = "https://top1.newkso.ru/top1/cdn"
CDN_DEFAULT = "newkso.ru"

def log(msg):
    LOGPATH = xbmcvfs.translatePath('special://logpath/')
    FILENAME = 'daddylivehd.log'
    LOG_FILE = os.path.join(LOGPATH, FILENAME)
    try:
        if isinstance(msg, str):
                _msg = f'\n    {msg}'

        else:
            raise TypeError('log() msg not of type str!')

        if not os.path.exists(LOG_FILE):
            f = open(LOG_FILE, 'w', encoding='utf-8')
            f.close()
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            line = ('[{} {}]: {}').format(datetime.now().date(), str(datetime.now().time())[:8], _msg)
            f.write(line.rstrip('\r\n') + '\n')
    except (TypeError, Exception) as e:
        try:
            xbmc.log(f'[ Daddylive ] Logging Failure: {e}', 2)
        except:
            pass


def preload_cache():
    global schedule_cache, cache_timestamp
    global livetv_cache, livetv_cache_timestamp

    now = time.time()

    # Preload LIVE SPORTS schedule
    try:
        hea = {
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': baseurl,
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-GPC': '1'
        }
        response = requests.get(schedule_url, headers=hea, timeout=10)
        if response.status_code == 200:
            schedule_cache = response.json()
            cache_timestamp = now
    except Exception as e:
        log(f"Failed to preload LIVE SPORTS schedule: {e}")

    # Preload LIVE TV channels
    try:
        livetv_cache = channels(fetch_live=True)
        livetv_cache_timestamp = now
    except Exception as e:
        log(f"Failed to preload LIVE TV channels: {e}")


def clean_category_name(name):
    """Cleans up HTML entities from sport categories."""
    if isinstance(name, str):
        # Decode HTML entities only
        name = html.unescape(name).strip()
    return name


def get_local_time(utc_time_str):
    time_format = addon.getSetting('time_format')

    if not time_format:
        time_format = '12h'

    try:
        event_time_utc = datetime.strptime(utc_time_str, '%H:%M')
    except TypeError:
        event_time_utc = datetime(*(time.strptime(utc_time_str, '%H:%M')[0:6]))

    user_timezone = addon.getSetting('epg_timezone')

    if not user_timezone:
        user_timezone = 0
    else:
        user_timezone = int(user_timezone)

    dst_enabled = addon.getSettingBool('dst_enabled')
    if dst_enabled:
        user_timezone += 1

    timezone_offset_minutes = user_timezone * 60
    event_time_local = event_time_utc + timedelta(minutes=timezone_offset_minutes)

    if time_format == '12h':
        local_time_str = event_time_local.strftime('%I:%M %p').lstrip('0')
    else:
        local_time_str = event_time_local.strftime('%H:%M')

    return local_time_str


def build_url(query):
    return addon_url + '?' + urlencode(query)


def addDir(title, dir_url, is_folder=True):
    li = xbmcgui.ListItem(title)
    labels = {'title': title, 'plot': title, 'mediatype': 'video'}
    kodiversion = getKodiversion()
    if kodiversion < 20:
        li.setInfo("video", labels)
    else:
        infotag = li.getVideoInfoTag()
        infotag.setMediaType(labels.get("mediatype", "video"))
        infotag.setTitle(labels.get("title", "Daddylive"))
        infotag.setPlot(labels.get("plot", labels.get("title", "Daddylive")))
    li.setArt({'thumb': '', 'poster': '', 'banner': '', 'icon': ICON, 'fanart': FANART})
    if is_folder is True:
        li.setProperty("IsPlayable", 'false')
    else:
        li.setProperty("IsPlayable", 'true')
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=dir_url, listitem=li, isFolder=is_folder)


def closeDir():
    xbmcplugin.endOfDirectory(addon_handle)


def getKodiversion():
    return int(xbmc.getInfoLabel("System.BuildVersion")[:2])


def Main_Menu():
    addDir('LIVE SPORTS', build_url({'mode': 'menu', 'serv_type': 'sched'}))
    addDir('LIVE TV', build_url({'mode': 'menu', 'serv_type': 'live_tv'}))

    li = xbmcgui.ListItem("Settings")
    li.setArt({'icon': ICON, 'fanart': FANART})
    li.setProperty("IsPlayable", "false")

    # Point to your addon with custom mode that opens settings
    url = build_url({'mode': 'open_settings'})
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=False)

    closeDir()



def getCategTrans():
    global schedule_cache, cache_timestamp
    hea = {
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': baseurl,  # Uses the same baseurl as Referer
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-GPC': '1'
    }
    categs = []

    now = time.time()

    try:
        # Use cache if it's still fresh
        if schedule_cache and (now - cache_timestamp) < cache_duration:
            schedule = schedule_cache
        else:
            # Download fresh schedule
            response = requests.get(schedule_url, headers=hea, timeout=10)
            if response.status_code == 200:
                schedule = response.json()
                schedule_cache = schedule
                cache_timestamp = now
            else:
                xbmcgui.Dialog().ok("Error", f"Failed to fetch data, status code: {response.status_code}")
                return []
    except Exception as e:
        xbmcgui.Dialog().ok("Error", f"Error fetching category data: {e}")
        return []

    try:
        for date_key, events in schedule.items():
            for categ, events_list in events.items():
                categ = clean_category_name(categ)
                categs.append((categ, json.dumps(events_list)))
    except Exception as e:
        log(f"Error parsing schedule: {e}")

    return categs



def Menu_Trans():
    categs = getCategTrans()
    if not categs:
        return

    for categ_name, events_list in categs:
        addDir(categ_name, build_url({'mode': 'showChannels', 'trType': categ_name}))
    closeDir()


def ShowChannels(categ, channels_list):
    # Special NBA filter for Basketball
    if categ.lower() == 'basketball':
        nba_channels = []
        for item in channels_list:
            title = item.get('title')
            if 'NBA' in title.upper():
                nba_channels.append(item)
        
        # Add NBA folder at the top
        if nba_channels:
            addDir('[NBA]', build_url({'mode': 'showNBA', 'trType': categ, 'nba_channels': json.dumps(nba_channels)}), True)

    # Always add the full list (unfiltered)
    for item in channels_list:
        title = item.get('title')
        addDir(title, build_url({'mode': 'trList', 'trType': categ, 'channels': json.dumps(item.get('channels'))}), True)
    
    closeDir()



def getTransData(categ):
    trns = []
    categs = getCategTrans()

    for categ_name, events_list_json in categs:
        if categ_name == categ:
            events_list = json.loads(events_list_json)
            for item in events_list:
                event = item.get('event')
                time_str = item.get('time')
                event_time_local = get_local_time(time_str)
                title = f'{event_time_local} {event}'
                channels = item.get('channels')
                
                # Fix: Accept both list and dict structures
                if isinstance(channels, dict):
                    # Convert dict to list of dicts
                    channels = list(channels.values())

                if isinstance(channels, list) and all(isinstance(channel, dict) for channel in channels):
                    trns.append({
                        'title': title,
                        'channels': [{'channel_name': channel.get('channel_name'), 'channel_id': channel.get('channel_id')} for channel in channels]
                    })
                else:
                    log(f"Unexpected data structure in 'channels' after conversion: {channels}")

    return trns



def TransList(categ, channels):
    for channel in channels:
        channel_title = html.unescape(channel.get('channel_name'))
        channel_id = channel.get('channel_id')
        addDir(channel_title, build_url({'mode': 'trLinks', 'trData': json.dumps({'channels': [{'channel_name': channel_title, 'channel_id': channel_id}]})}), False)
    closeDir()


def getSource(trData):
    data = json.loads(unquote(trData))

    channels_data = data.get('channels')

    if channels_data is not None and isinstance(channels_data, list):
        url_stream = f'{baseurl}stream/stream-{channels_data[0]["channel_id"]}.php'
        xbmcplugin.setContent(addon_handle, 'videos')
        PlayStream(url_stream)


def list_gen():
    addon_url = baseurl
    chData = channels()
    for c in chData:
        addDir(c[1], build_url({'mode': 'play', 'url': addon_url + c[0]}), False)
    closeDir()


def channels(fetch_live=False):

    global livetv_cache, livetv_cache_timestamp

    if not fetch_live:
        now = time.time()
        if livetv_cache and (now - livetv_cache_timestamp) < cache_duration:
            return livetv_cache
    
    url = baseurl + '/24-7-channels.php'
    do_adult = xbmcaddon.Addon().getSetting('adult_pw')

    hea = {
        'Referer': baseurl + '/',
        'user-agent': UA,
    }

    resp = requests.post(url, headers=hea).text
    ch_block = re.compile('<center><h1(.+?)tab-2', re.MULTILINE | re.DOTALL).findall(str(resp))
    chan_data = re.compile('href=\"(.*)\" target(.*)<strong>(.*)</strong>').findall(ch_block[0])

    channels = []
    for c in chan_data:
        if not "18+" in c[2]:
            channels.append([c[0], c[2]])
        if do_adult == 'lol' and "18+" in c[2]:
            channels.append([c[0], c[2]])

    return channels


def PlayStream(link):
    """
    Final working PlayStream using the tested patterns
    """
    headers = {'Referer': baseurl, 'user-agent': UA}

    try:
        # Extract stream ID
        stream_id_match = re.search(r'stream-(\d+)\.php', link)
        if not stream_id_match:
            log("Could not extract stream ID from link")
            xbmcgui.Dialog().ok("Playback Error", "Invalid stream URL format.")
            return
        
        stream_id = stream_id_match.group(1)
        channel_key = f"premium{stream_id}"
        log(f"Stream ID: {stream_id}, Channel Key: {channel_key}")

        # Headers that work (from test results)
        stream_headers = {
            'Origin': 'https://yoxplay.xyz',
            'Referer': 'https://yoxplay.xyz/',
            'user-agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0',
            'Accept': '*/*',
        }

        # Step 1: Get server_key from yoxplay.xyz (this works!)
        server_key = None
        try:
            lookup_url = f"https://yoxplay.xyz/server_lookup.php?channel_id={channel_key}"
            log(f"Getting server key from: {lookup_url}")
            
            lookup_resp = requests.get(lookup_url, headers=stream_headers, timeout=10)
            lookup_resp.raise_for_status()
            
            lookup_data = lookup_resp.json()
            server_key = lookup_data.get('server_key')
            log(f"Server lookup response: {lookup_data}")
            
            if server_key:
                log(f"✅ Got server_key: {server_key}")
            else:
                log("❌ No server_key in response")
                
        except Exception as e:
            log(f"Server lookup failed: {e}")

        # Step 2: Build M3U8 URL based on server_key
        if server_key == "top1/cdn":
            m3u8_url = f"https://top1.newkso.ru/top1/cdn/{channel_key}/mono.m3u8"
        elif server_key and "/" not in server_key:
            # Dynamic pattern: {server_key}new.newkso.ru/{server_key}/
            # Examples: zeko → zekonew.newkso.ru/zeko/, ddy6 → ddy6new.newkso.ru/ddy6/
            m3u8_url = f"https://{server_key}new.newkso.ru/{server_key}/{channel_key}/mono.m3u8"
            log(f"Using dynamic server pattern for {server_key}")
        else:
            # Fallback to zeko pattern
            log("Using fallback zeko pattern")
            m3u8_url = f"https://zekonew.newkso.ru/zeko/{channel_key}/mono.m3u8"

        log(f"M3U8 URL: {m3u8_url}")

        # Step 3: Test if M3U8 is accessible
        try:
            test_resp = requests.head(m3u8_url, headers=stream_headers, timeout=10)
            test_resp.raise_for_status()
            log(f"✅ M3U8 accessible: HTTP {test_resp.status_code}")
        except Exception as e:
            log(f"❌ M3U8 test failed: {e}")
            
            # Try fallback patterns if original failed
            fallback_tried = False
            if server_key and server_key not in m3u8_url:
                # Try the dynamic pattern if we haven't already
                fallback_url = f"https://{server_key}new.newkso.ru/{server_key}/{channel_key}/mono.m3u8"
                log(f"Trying dynamic pattern fallback: {fallback_url}")
                try:
                    test_resp = requests.head(fallback_url, headers=stream_headers, timeout=10)
                    test_resp.raise_for_status()
                    m3u8_url = fallback_url
                    log(f"✅ Dynamic pattern fallback works")
                    fallback_tried = True
                except Exception as e2:
                    log(f"❌ Dynamic pattern fallback failed: {e2}")
            
            if not fallback_tried and 'zekonew.newkso.ru' not in m3u8_url:
                # Try zeko fallback
                fallback_url = f"https://zekonew.newkso.ru/zeko/{channel_key}/mono.m3u8"
                log(f"Trying zeko fallback: {fallback_url}")
                try:
                    test_resp = requests.head(fallback_url, headers=stream_headers, timeout=10)
                    test_resp.raise_for_status()
                    m3u8_url = fallback_url
                    log(f"✅ Zeko fallback works")
                except Exception as e3:
                    log(f"❌ All fallbacks failed: {e3}")
                    xbmcgui.Dialog().ok("Playback Error", f"Stream not accessible: {e}")
                    return

        # Step 4: Build final Kodi playback URL with proper headers
        origin = quote_plus('https://yoxplay.xyz')
        referer = quote_plus('https://yoxplay.xyz/')
        ua = quote_plus(stream_headers['user-agent'])
        
        final_link = (
            f"{m3u8_url}|"
            f"Origin={origin}&"
            f"Referer={referer}&"
            f"User-Agent={ua}&"
            f"Keep-Alive=true"
        )

        log(f"Final playback URL: {final_link}")

        # Step 5: Start playback
        liz = xbmcgui.ListItem('Daddylive', path=final_link)
        liz.setProperty('inputstream','inputstream.ffmpegdirect')
        liz.setMimeType('application/x-mpegURL')
        liz.setProperty('inputstream.ffmpegdirect.is_realtime_stream','true')
        liz.setProperty('inputstream.ffmpegdirect.stream_mode','timeshift')
        liz.setProperty('inputstream.ffmpegdirect.manifest_type','hls')
        xbmcplugin.setResolvedUrl(addon_handle, True, liz)

        log("🎯 Playback started successfully")

    except Exception as e:
        log(f"PlayStream error: {e}")
        log(traceback.format_exc())
        xbmcgui.Dialog().ok("Playback Error", f"Streaming failed: {str(e)}")

        
kodiversion = getKodiversion()
mode = params.get('mode', None)

if not mode:
    preload_cache()
    Main_Menu()
else:
    if mode == 'menu':
        servType = params.get('serv_type')
        if servType == 'sched':
            Menu_Trans()
        if servType == 'live_tv':
            list_gen()

    if mode == 'showChannels':
        transType = params.get('trType')
        channels = getTransData(transType)
        ShowChannels(transType, channels)

    if mode == 'trList':
        transType = params.get('trType')
        channels = json.loads(params.get('channels'))
        TransList(transType, channels)

    if mode == 'trLinks':
        trData = params.get('trData')
        getSource(trData)

    if mode == 'play':
        link = params.get('url')
        PlayStream(link)
        
    if mode == 'open_settings':
        xbmcaddon.Addon().openSettings()
        xbmcplugin.endOfDirectory(addon_handle)
        
    if mode == 'showNBA':
        transType = params.get('trType')
        nba_channels = json.loads(params.get('nba_channels'))
        ShowChannels(transType, nba_channels)