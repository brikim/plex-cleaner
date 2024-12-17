#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
From a list of TV shows, check if users in a list has watched shows episodes.
If all users in list have watched an episode of listed show, then delete episode.

Add deletion via Plex.
"""
from __future__ import print_function
from __future__ import unicode_literals

import requests
import sys
import os
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from deleteEmptyFolders import delete_empty_folders

@dataclass
class LibraryInfo:
    plexLibraryName: str
    embyLibraryName: str
    plexContainerPath: str
    embyContainerPath: str
    physicalPath: str
    plexLibraryId: str
    embyLibraryId: str

scriptEnabled = False
scriptName = 'DeleteWatchedTv'
conf_loc_path_file = ''
tautulli_url = ''
tautulli_api_key = ''
plex_url = ''
plex_api_key = ''
plex_valid = True
emby_url = ''
emby_api_key = ''
emby_valid = True
jellystat_url = ''
jellystat_api_key = ''
jellystat_valid = True
library_list = []
library_path = []
libraries = []
plex_user_list = []
emby_user_list = []
delete_time_hours = 24

if "ENABLED_DELETE_WATCHED_TV" in os.environ:
    scriptEnabled = os.environ['ENABLED_DELETE_WATCHED_TV'] == '1'

if "CONFIG_PATH_FILE" in os.environ:
    conf_loc_path_file = os.environ['CONFIG_PATH_FILE'].rstrip('/')

def get_tautulli_api_url():
    return tautulli_url.rstrip('/') + '/api/v2'
    
def setup_plex_libraries():
    try:
        payload = {
            'apikey': tautulli_api_key,
            'cmd': 'get_libraries'}
        
        r = requests.get(get_tautulli_api_url(), params=payload)
        response = r.json()
        res_data = response['response']['data']
        
        for tautLib in res_data:
            for lib in libraries:
                if (tautLib['section_name'] == lib.plexLibraryName):
                    lib.plexLibraryId = tautLib['section_id']
    except Exception as e:
        sys.stderr.write("{}: Tautulli API 'get_libraries' request failed: {}.\n".format(scriptName, e))
        
def setup_jellystat_libraries():
    try:
        headers = {
            'x-api-token': jellystat_api_key,
            "Content-Type": "application/json"}
        payload = {}
    
        jellystatR = requests.get(jellystat_url.rstrip('/') + '/api/getLibraries', headers=headers, params=payload)
        jellystatResponse = jellystatR.json()
        for jellyLib in jellystatResponse:
            for lib in libraries:
                if jellyLib['Name'] == lib.embyLibraryName:
                    lib.embyLibraryId = jellyLib['Id']
    except Exception as e:
        sys.stderr.write("{}: Jellystat API 'get_libraries' request failed: {}.\n".format(scriptName, e))

def get_filename(key):
    # Get the metadata for a media item.
    payload = {
        'apikey': tautulli_api_key,
        'rating_key': str(key),
        'cmd': 'get_metadata'}

    try:
        r = requests.get(get_tautulli_api_url(), params=payload)
        response = r.json()

        res_data = response['response']['data']
        if (len(res_data) > 0):
            return res_data['media_info'][0]['parts'][0]['file']
        else:
            return ""

    except Exception as e:
        sys.stderr.write("{}: Tautulli API 'get_metadata' request failed: {}.\n".format(scriptName, e))
        pass

def hours_since_play(useUtcTime, playDateTime):
    currentDateTime = datetime.now(timezone.utc) if useUtcTime == True else datetime.now()
    time_difference = currentDateTime - playDateTime
    return (time_difference.days * 24) + (time_difference.seconds / 3600)

def find_plex_watched_shows(user, library):
    # Get the Tautulli history.
    payload = {
        'apikey': tautulli_api_key,
        'cmd': 'get_history',
        'user': user,
        'section_id': library.plexLibraryId}

    try:
        r = requests.get(get_tautulli_api_url(), params=payload)
        response = r.json()
        res_data = response['response']['data']['data']
        
        returnFileNames = []
        for item in res_data:
            if item['watched_status'] == 1:
                fileName = get_filename(item['rating_key'])
                if len(fileName) > 0:
                    hoursSincePlay = hours_since_play(False, datetime.fromtimestamp(item['stopped']))
                    if hoursSincePlay >= delete_time_hours:
                        returnFileNames.append(fileName.replace(library.plexContainerPath, library.physicalPath))
                    else:
                        if hoursSincePlay >= (delete_time_hours * 0.7):
                            sys.stdout.write("{}: Pending Delete. Plex watched {:.1f} hours ago will delete at {} hours. {}\n".format(scriptName, hoursSincePlay, delete_time_hours, fileName))
        
        return returnFileNames
    
    except Exception as e:
        sys.stderr.write("{}: Tautulli API 'get_history' request failed: {}.\n".format(scriptName, e))

def find_emby_watched_status(userName, id, watchedTimeStr):
    payload = {
        'api_key': emby_api_key,
        'id': id}
    r = requests.get(emby_url.rstrip('/') + '/emby/user_usage_stats/get_item_stats', params=payload)
    response = r.json()
    for userActivity in response:
        if userActivity['name'] == userName and userActivity['played'] == 'True':
            return hours_since_play(True, datetime.fromisoformat(watchedTimeStr))
    return 0.0
    
def find_emby_watched_shows(library):
    try:
        headers = {
            'x-api-token': jellystat_api_key,
            "Content-Type": "application/json"}
        payload = {
            'libraryid': library.embyLibraryId}
        r = requests.post(jellystat_url.rstrip('/') + '/api/getLibraryHistory', headers=headers, data=json.dumps(payload))
        response = r.json()
        
        returnFileNames = []
        for item in response:
            if item['UserName'] in emby_user_list:
                hoursSincePlay = find_emby_watched_status(item['UserName'], item['NowPlayingItemId'], item['ActivityDateInserted'])
                if hoursSincePlay >= delete_time_hours:
                    payload = {
                        'Id': item['NowPlayingItemId']}
                    detailR = requests.post(jellystat_url.rstrip('/') + '/api/getItemDetails', headers=headers, data=json.dumps(payload))
                    detailResponse = detailR.json()
                    for itemDetail in detailResponse:
                        fileName = itemDetail['Path']
                        returnFileNames.append(fileName.replace(library.embyContainerPath, library.physicalPath))
                else:
                    if hoursSincePlay >= (delete_time_hours * 0.7):
                        sys.stdout.write("{}: Pending Delete. Emby watched {:.1f} hours ago will delete at {} hours. {}\n".format(scriptName, hoursSincePlay, delete_time_hours, fileName))
        
        return returnFileNames
    
    except Exception as e:
        sys.stderr.write("{}: Jellystat API 'GetLibraryHistory' request failed: {}.\n".format(scriptName, e))
    
if scriptEnabled == True:
    if os.path.exists(conf_loc_path_file) == True:
        goodConfigRead = True
            
        try:
            # Opening JSON file
            f = open(conf_loc_path_file, 'r')

            # returns JSON object as a dictionary
            data = json.load(f)
            
            tautulli_url = data['tautulli_url']
            tautulli_api_key = data['tautulli_api_key']
            config = data['delete_watched_shows']
            delete_time_hours = config['delete_time_hours']
            for user in config['users']:
                plex_user_list.append(user['plexName'])
                if jellystat_valid == True and 'embyName' in user:
                    emby_user_list.append(user['embyName'])
                else:
                    jellystat_valid = False
            for library in config['libraries']:
                embyLibraryName = ''
                embyLibraryPath = ''
                if ('embyLibraryName' in library) and ('embyContainerPath' in library):
                    embyLibraryName = library['embyLibraryName']
                    embyContainerPath = library['embyContainerPath']
                else:
                    jellystat_valid = False
                    
                libraries.append(LibraryInfo(library['plexLibraryName'], embyLibraryName, library['plexContainerPath'], embyContainerPath, library['physicalLibraryPath'], '', ''))
        except Exception as e:
            sys.stderr.write("{}: ERROR Reading Config file {}\n".format(scriptName, e))
            goodConfigRead = False

        try:
            plex_url = data['plex_url']
            plex_api_key = data['plex_api_key']
            if (plex_url == '' or plex_api_key == ''):
                plex_valid = False
        except Exception as e:
            plex_valid = False
        
        try:
            emby_url = data['emby_url']
            emby_api_key = data['emby_api_key']
            if emby_url == '' or emby_api_key == '':
                emby_valid = False
        except Exception as e:
            emby_valid = False
        
        if jellystat_valid == True:
            try:
                jellystat_url = data['jellystat_url']
                jellystat_api_key = data['jellystat_api_key']
                if jellystat_url == '' or jellystat_api_key == '':
                    jellystat_valid = False
            except Exception as e:
                jellystat_valid = False
                        
        if (goodConfigRead == True):
            showsToDelete = []
            
            # Setup plex library ids
            setup_plex_libraries()
            
            # Find plex shows to delete
            for plexUser in plex_user_list:
                for lib in libraries:
                    showsToDelete.append(find_plex_watched_shows(plexUser, lib))
                    
            # Setup jellystat library ids if valid
            if jellystat_valid == True and emby_valid == True:
                setup_jellystat_libraries()
                
                # Find jellystat watched shows
                for lib in libraries:
                    showsToDelete.append(find_emby_watched_shows(lib))
            
            try:
                numberOfDeletedShows = 0
                for shows in showsToDelete:
                    for show in shows:
                        os.remove(show)
                        sys.stdout.write("{}: Deleted File: {}\n".format(scriptName, show))
                        numberOfDeletedShows += 1
            except Exception as e:
                sys.stderr.write("{}: Error Deleting File {}\n".format(scriptName, e))
            
            if numberOfDeletedShows > 0:
                # Clean up empty folders in paths
                checkEmptyFolderPaths = []
                for lib in libraries:
                    checkEmptyFolderPaths.append(lib.physicalPath)
                delete_empty_folders(checkEmptyFolderPaths, scriptName)
                
                if plex_valid == True:
                    session = requests.Session()
                    session.verify = False

                    for lib in libraries:
                        try:
                            plexCommandUrl = plex_url.rstrip('/') + "/library/sections/" + lib.plexLibraryId + "/refresh?path=" + lib.plexContainerPath + "&X-Plex-Token=" + plex_api_key
                            session.get(plexCommandUrl, headers={"Accept":"application/json"})
                            sys.stdout.write("{}: Notifying Plex to Refresh\n".format(scriptName))
                        except Exception as e:
                            sys.stderr.write("{}: Plex API 'sections refresh' request failed: {}.\n".format(scriptName, e))

                if emby_valid == True:
                    try:
                        embyRefreshUrl = emby_url.rstrip('/') + '/emby/Library/Refresh?api_key=' + emby_api_key
                        embyResponse = requests.post(embyRefreshUrl)
                        sys.stdout.write("{}: Notifying Emby to Refresh\n".format(scriptName))
                    except Exception as e:
                            sys.stderr.write("{}: Emby API 'library refresh' request failed: {}.\n".format(scriptName, e))
                
