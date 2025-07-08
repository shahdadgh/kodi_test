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
    Simplified PlayStream using the premium{id} pattern
    """
    headers = {'Referer': baseurl, 'user-agent': UA}

    try:
        # 1) Extract stream ID from the original link
        stream_id_match = re.search(r'stream-(\d+)\.php', link)
        if not stream_id_match:
            log("Could not extract stream ID from link")
            xbmcgui.Dialog().ok("Playback Error", "Invalid stream URL format.")
            return
        
        stream_id = stream_id_match.group(1)
        log(f"Stream ID: {stream_id}")

        # 2) Get the main iframe page to find mirrors
        resp0 = requests.post(link, headers=headers, timeout=10).text
        
        # Find main iframe
        all_iframes = re.findall(r'iframe[^>]*src=["\']([^"\']+)["\']', resp0, re.IGNORECASE)
        main_iframe_url = None
        for src in all_iframes:
            if 'thedaddy.to/embed/stream-' in src:
                main_iframe_url = src
                break
        
        if not main_iframe_url:
            log("Main iframe not found")
            xbmcgui.Dialog().ok("Playback Error", "Could not find streaming iframe.")
            return

        # 3) Get nested iframe to extract mirrors
        resp1 = requests.post(main_iframe_url, headers=headers, timeout=10).text
        nested_iframes = re.findall(r'iframe[^>]*src=["\']([^"\']+)["\']', resp1, re.IGNORECASE)
        
        nested_iframe_url = None
        for src in nested_iframes:
            if 'yoxplay.xyz' in src and ('daddyhd.php' in src or 'daddylivehd.php' in src):
                nested_iframe_url = src
                break
        
        if not nested_iframe_url:
            log("Nested iframe not found")
            # Continue anyway - we can try without mirrors
            mirrors = []
        else:
            # 4) Get mirrors from nested iframe
            try:
                headers_nested = {'Referer': main_iframe_url, 'user-agent': UA}
                resp2 = requests.get(nested_iframe_url, headers=headers_nested, timeout=10).text
                
                encoded_match = re.search(r'encodedDomains["\'\s]*[=:]["\'\s]*["\']([^"\']+)["\']', resp2)
                if encoded_match:
                    decoded = base64.b64decode(encoded_match.group(1)).decode('utf-8')
                    mirrors = json.loads(decoded)
                    log(f"Found {len(mirrors)} mirrors")
                else:
                    mirrors = []
            except Exception as e:
                log(f"Error getting mirrors: {e}")
                mirrors = []

        # 5) Use the premium{id} pattern we discovered
        channel_key = f"premium{stream_id}"
        log(f"Using channel_key: {channel_key}")

        # 6) Try main CDN first, then mirrors
        hosts_to_try = ['top1.newkso.ru'] + mirrors[:10]  # Limit to first 10 mirrors for speed

        last_error = None
        for i, host in enumerate(hosts_to_try):
            try:
                log(f"Trying host {i+1}/{len(hosts_to_try)}: {host}")
                
                # Try the direct CDN approach first (skip auth.php for now)
                if host == 'top1.newkso.ru':
                    m3u8 = f"{CDN1_BASE}/{channel_key}/mono.m3u8"
                    host_root = f"https://{host}"
                else:
                    # For mirror hosts, try to get server_key
                    try:
                        # Use dummy auth values - they might not be needed
                        auth_url = (
                            f"{AUTH_SERVER}/auth.php?"
                            f"channel_id={channel_key}"
                            f"&ts=1&rnd=1&sig=1"
                        )
                        r_auth = requests.get(auth_url, headers=headers, timeout=5)
                        
                        # Try server_lookup
                        host_root = f"https://{host}"
                        lookup_url = f"{host_root}/server_lookup.php?channel_id={channel_key}"
                        r_lookup = requests.get(lookup_url, headers=headers, timeout=5)
                        r_lookup.raise_for_status()
                        
                        lookup_data = r_lookup.json()
                        server_key = lookup_data.get('server_key')
                        if server_key == "top1/cdn":
                            m3u8 = f"{CDN1_BASE}/{channel_key}/mono.m3u8"
                        else:
                            m3u8 = f"https://{server_key}.{CDN_DEFAULT}/{server_key}/{channel_key}/mono.m3u8"
                    except:
                        # Fallback: assume same pattern as main CDN
                        m3u8 = f"https://{host}/cdn/{channel_key}/mono.m3u8"
                        host_root = f"https://{host}"

                log(f"Testing M3U8: {m3u8}")

                # 7) Test if the M3U8 URL is accessible
                test_resp = requests.head(m3u8, headers={'Referer': host_root, 'user-agent': UA}, timeout=5)
                if test_resp.status_code not in [200, 302]:
                    raise Exception(f"M3U8 not accessible: {test_resp.status_code}")

                # 8) Build final playback URL with headers
                ref = quote_plus(host_root)
                ua = quote_plus(UA)
                final_link = f"{m3u8}|Referer={ref}&Origin={ref}&User-Agent={ua}&Keep-Alive=true"

                log(f"Final playback URL: {final_link}")

                # 9) Start playback
                liz = xbmcgui.ListItem('Daddylive', path=final_link)
                liz.setProperty('inputstream','inputstream.ffmpegdirect')
                liz.setMimeType('application/x-mpegURL')
                liz.setProperty('inputstream.ffmpegdirect.is_realtime_stream','true')
                liz.setProperty('inputstream.ffmpegdirect.stream_mode','timeshift')
                liz.setProperty('inputstream.ffmpegdirect.manifest_type','hls')
                xbmcplugin.setResolvedUrl(addon_handle, True, liz)

                log("Playback started successfully")
                return

            except Exception as e:
                last_error = e
                log(f"Host {host} failed: {e}")

        # If we get here, all hosts failed
        log(f"All hosts failed. Last error: {last_error}")
        xbmcgui.Dialog().ok("Playback Error", f"All streaming hosts failed. Last error: {str(last_error)}")

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