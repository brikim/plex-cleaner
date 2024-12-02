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
from datetime import datetime
from dataclasses import dataclass

@dataclass
class LibraryInfo:
    name: str
    plexPath: str
    physicalPath: str
    plexLibraryId: str

scriptEnabled = False
conf_loc_path_file = ''
plex_url = ''
plex_api_key = ''
tautulli_url = ''
tautulli_api_key = ''
library_list = []
library_path = []
libraries = []
user_list = []
delete_time_hours = 24

if "ENABLED_DELETE_WATCHED_TV" in os.environ:
    scriptEnabled = os.environ['ENABLED_DELETE_WATCHED_TV'] == '1'

if "CONFIG_PATH_FILE" in os.environ:
    conf_loc_path_file = os.environ['CONFIG_PATH_FILE'].rstrip('/')

def get_tautulli_api_url():
    return tautulli_url.rstrip('/') + '/api/v2'
    
def setup_libraries():
    payload = {
        'apikey': tautulli_api_key,
        'cmd': 'get_libraries'}
    try:
        r = requests.get(get_tautulli_api_url(), params=payload)
        response = r.json()
        res_data = response['response']['data']
        
        for tautLib in res_data:
            for lib in libraries:
                if (tautLib['section_name'] == lib.name):
                    lib.plexLibraryId = tautLib['section_id']

    except Exception as e:
        sys.stderr.write("Tautulli API 'get_libraries' request failed: {0}.\n".format(e))
        pass

def get_filename(key):
    # Get the metadata for a media item.
    payload = {
        'apikey': tautulli_api_key,
        'rating_key': str(key),
        'cmd': 'get_metadata'}
        #'media_info': True}

    try:
        r = requests.get(get_tautulli_api_url(), params=payload)
        response = r.json()

        res_data = response['response']['data']
        if (len(res_data) > 0):
            return res_data['media_info'][0]['parts'][0]['file']
        else:
            return ""

    except Exception as e:
        sys.stderr.write("Tautulli API 'get_metadata' request failed: {0}.\n".format(e))
        pass

def find_watched_shows(user, library):
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
                    time_difference = datetime.now() - datetime.fromtimestamp(item['stopped'])
                    hoursSincePlay = (time_difference.days * 24) + (time_difference.seconds / 3600)
                    if hoursSincePlay >= delete_time_hours:
                        returnFileNames.append(fileName.replace(library.plexPath, library.physicalPath))
                    else:
                        sys.stdout.write("Pending Delete. File watched {:.1f} hours ago will delete at {} hours. {}\n".format(hoursSincePlay, delete_time_hours, fileName))
        
        return returnFileNames

    except Exception as e:
        sys.stderr.write("Tautulli API 'get_history' request failed: {0}.\n".format(e))

if scriptEnabled == True:
    if os.path.exists(conf_loc_path_file) == True:
        try:
            goodConfigRead = True
            
            # Opening JSON file
            f = open(conf_loc_path_file, 'r')

            # returns JSON object as a dictionary
            data = json.load(f)
            
            plex_url = data['plex_url']
            plex_api_key = data['plex_api_key']
            tautulli_url = data['tautulli_url']
            tautulli_api_key = data['tautulli_api_key']
            
            config = data['delete_watched_shows']
            delete_time_hours = config['delete_time_hours']
            for user in config['users']:
                user_list.append(user['name'])
            for library in config['libraries']:
                libraries.append(LibraryInfo(library['plexLibraryName'], library['plexLibraryPath'], library['physicalLibraryPath'], ''))
        except Exception as e:
            sys.stderr.write("DeleteWatchedTv: ERROR Reading Config file {}\n".format(e))   
            goodConfigRead = False
        
        if (goodConfigRead == True):
            showsToDelete = []
            setup_libraries()
            for user in user_list:
                for lib in libraries:
                    showsToDelete.append(find_watched_shows(user, lib))
            
            numberOfDeletedShows = 0
            for shows in showsToDelete:
                for show in shows:
                    sys.stdout.write("Deleting File: {}\n".format(show))
                    os.remove(show)
                    numberOfDeletedShows = numberOfDeletedShows + 1
            
            if (numberOfDeletedShows > 0):
                sys.stdout.write("Notifying Plex to Refresh\n")
                session = requests.Session()
                session.verify = False

                for lib in libraries:
                    try:
                        plexCommandUrl = plex_url + "/library/sections/" + lib.plexLibraryId + "/refresh?path=" + lib.plexPath + "&X-Plex-Token=" + plex_api_key
                        session.get(plexCommandUrl, headers={"Accept":"application/json"})
                    except Exception as e:
                        sys.stderr.write("Plex API 'sections refresh' request failed: {0}.\n".format(e))
