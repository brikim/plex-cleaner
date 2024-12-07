#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
From a config file delete shows that meet a certain criteria
"""
from __future__ import print_function
from __future__ import unicode_literals

import sys
import os
import json
import glob
import requests
from datetime import datetime
from dataclasses import dataclass

@dataclass
class FileInfo:
    path: str
    ageDays: float
    
run_test = False
scriptEnabled = False
scriptName = 'DeleteOldTv'
conf_loc_path_file = ''
tautulli_url = ''
tautulli_api_key = ''
plex_url = ''
plex_api_key = ''
plex_valid = True
emby_url = ''
emby_api_key = ''
emby_valid = True
library_path = ''

if "ENABLED_DELETE_OLD_TV" in os.environ:
    scriptEnabled = os.environ['ENABLED_DELETE_OLD_TV'] == '1'

if "CONFIG_PATH_FILE" in os.environ:
    conf_loc_path_file = os.environ['CONFIG_PATH_FILE'].rstrip('/')

def deleteShow(pathFileName):
    if run_test == True:
        sys.stdout.write("{}: Running Test! Would delete {}\n".format(scriptName, pathFileName))
    else:
        os.remove(pathFileName)
    
def get_files_in_path(path):
    fileInfo = []
    for file in glob.glob(path + "/**/*", recursive=True):
        if file.endswith(".ts") or file.endswith(".mkv"):
            fileAge = datetime.now() - datetime.fromtimestamp(os.path.getmtime(file))
            fileInfo.append(FileInfo(file, fileAge.days + (fileAge.seconds / 86400)))
    return fileInfo
    
def keep_last_show_delete(path, keepLast):
    showsDeleted = False
    fileInfo = get_files_in_path(path)
    if len(fileInfo) > keepLast:
        showsToDelete = len(fileInfo) - keepLast
        sys.stdout.write("{}: KEEP_LAST - Show {} need to delete {} shows\n".format(scriptName, path, showsToDelete))
        try:
            sortedFileInfo = sorted(fileInfo, key=lambda item: item.ageDays, reverse=True)
            
            deletedShows = 0
            for file in sortedFileInfo:
                sys.stdout.write("{}: KEEP_LAST - Deleting Show-{}\n".format(scriptName, file.path))
                deleteShow(file.path)
                showsDeleted = True
                
                deletedShows = deletedShows + 1
                if deletedShows >= showsToDelete:
                    break

        except Exception as e:
                sys.stderr.write("{}: KEEP_LAST error sorting files {}\n".format(scriptName, e))
    
    return showsDeleted
                
def keep_show_days(path, keepDays):
    showsDeleted = False
    fileInfo = get_files_in_path(path)
    for file in fileInfo:
        if file.ageDays >= keepDays:
            sys.stdout.write("{}: KEEP_DAYS - Deleting Show-{} Age-{} Older than Keep Days-{}\n".format(scriptName, file.path,file.ageDays,keepDays))
            deleteShow(file.path)
            showsDeleted = True
    return showsDeleted
    
def check_show_delete(config):
    deletedShowPlexLibraries = []
    libraryFilePath = config['physicalLibraryPath'].rstrip('/') + '/' + config['name']
    if os.path.exists(libraryFilePath) == True:
        if config['action'].find('KEEP_LAST_') != -1:
            try:
                keepLastNum = int(config['action'].replace('KEEP_LAST_', ''))
                showsDeleted = keep_last_show_delete(libraryFilePath, keepLastNum)
                if showsDeleted == True:
                    deletedShowPlexLibraries.append(config['plexLibraryName'])
            except Exception as e:
                sys.stderr.write("{}: Value after KEEP_LAST_ {} not a number!\n".format(scriptName, e))
        elif config['action'].find('KEEP_LENGTH_DAYS_') != -1:
            try:
                keepLengthDays = int(config['action'].replace('KEEP_LENGTH_DAYS_', ''))
                showsDeleted = keep_show_days(libraryFilePath, keepLengthDays)
                if showsDeleted == True:
                    deletedShowPlexLibraries.append(config['plexLibraryName'])
            except Exception as e:
                sys.stderr.write("{}: Value after KEEP_LENGTH_DAYS_ {} not a number!\n".format(scriptName, e))
    
    return deletedShowPlexLibraries

def get_plex_library_id(libName):
    payload = {
        'apikey': tautulli_api_key,
        'cmd': 'get_libraries'}
    try:
        r = requests.get(tautulli_url.rstrip('/') + '/api/v2', params=payload)
        response = r.json()
        res_data = response['response']['data']
        
        libraryId = -1
        for tautLib in res_data:
            if (tautLib['section_name'] == libName):
                libraryId = tautLib['section_id']
                break
        return libraryId

    except Exception as e:
        sys.stderr.write("{}: Tautulli API 'get_libraries' request failed: {}.\n".format(scriptName, e))
        pass

def delete_empty_folders(pathsToCheck):
    # Delete empty folders in physical path if any exist
    for path in pathsToCheck:
        folderRemoved = True
        while folderRemoved == True:
            folderRemoved = False
            for dirpath, dirnames, filenames in os.walk(path, topdown=False):
                if not dirnames and not filenames:
                    os.rmdir(dirpath)
                    folderRemoved = True

def notify_plex_refresh(deletedShowLibs):
    plexLibIds = []
    if plex_valid == True:
        for lib in deletedShowLibs:
            libId = get_plex_library_id(lib)
            if libId != '-1':
                plexLibIds.append(libId)
                session = requests.Session()
                session.verify = False
                try:
                    plexCommandUrl = plex_url + "/library/sections/" + libId + "/refresh?X-Plex-Token=" + plex_api_key
                    session.get(plexCommandUrl, headers={"Accept":"application/json"})
                    sys.stdout.write("{}: Notifying Plex to Refresh\n".format(scriptName))
                except Exception as e:
                    sys.stderr.write("{}: Plex API 'sections refresh' request failed: {}.\n".format(scriptName, e))

def notify_emby_refresh():
    if emby_valid == True:
        try:
            embyRefreshUrl = emby_url.rstrip('/') + '/emby/Library/Refresh?api_key=' + emby_api_key
            requests.post(embyRefreshUrl)
            sys.stdout.write("{}: Notifying Emby to Refresh\n".format(scriptName))
        except Exception as e:
            sys.stderr.write("{}: Emby API 'library refresh' request failed: {}.\n".format(scriptName, e))

if scriptEnabled == True:
    if os.path.exists(conf_loc_path_file) == True:
        try:
            # Opening JSON file
            f = open(conf_loc_path_file, 'r')
            data = json.load(f)
            
            tautulli_url = data['tautulli_url']
            tautulli_api_key = data['tautulli_api_key']
            deleteOldShowsConfig = data['delete_old_shows']
        except Exception as e:
            sys.stderr.write("{}: Error with config file {}\n".format(scriptName, e))
        
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
            
        try:
            physicalPathsToCheckForDelete = []
            plexLibrariesToRefresh = []
            # Iterating through the json list
            for i in deleteOldShowsConfig['show_details']:
                deletedShows = check_show_delete(i)
                if len(deletedShows) > 0:
                    physicalPathsToCheckForDelete.append(i['physicalLibraryPath'])
                for show in deletedShows:
                    plexLibrariesToRefresh.append(show)
            
            delete_empty_folders(list(set(physicalPathsToCheckForDelete)))
            notify_plex_refresh(list(set(plexLibrariesToRefresh)))
            if len(plexLibrariesToRefresh) > 0:
                notify_emby_refresh()
        except Exception as e:
            sys.stderr.write("{}: Error with config file {}\n".format(scriptName, e))
    else:
        sys.stderr.write("{}: config file set but {} does not exist!\n".format(scriptName, conf_loc_path_file))