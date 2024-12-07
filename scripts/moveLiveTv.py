#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
From a list of TV shows, check if users in a list has watched shows episodes.
If all users in list have watched an episode of listed show, then delete episode.

Add deletion via Plex.
"""
from __future__ import print_function
from __future__ import unicode_literals

import sys
import os
import glob
import shutil
import json
from datetime import datetime

scriptEnabled = False
scriptName = 'MoveLiveTv'
conf_loc_path_file = ''
plex_grab_folder = ''
move_to_folder = ''
move_time_hours = 2
change_owner = False
change_owner_uid = 0
change_owner_gid = 0

if "ENABLED_MOVE_LIVE_TV" in os.environ:
    scriptEnabled = os.environ['ENABLED_MOVE_LIVE_TV'] == '1'
    
if "CONFIG_PATH_FILE" in os.environ:
    conf_loc_path_file = os.environ['CONFIG_PATH_FILE'].rstrip('/')

def move_file(filePath):
    correctedFilePath = filePath.replace('\\', '/')
    
    showNameStartIndex = correctedFilePath.rfind('/')
    showName = filePath[showNameStartIndex+1:filePath.find('-')-1]
    newShowPath = move_to_folder + '/' + showName
    
    if os.path.isdir(newShowPath) == False:
        os.mkdir(newShowPath)
        if change_owner == True:
            os.chown(newShowPath, change_owner_uid, change_owner_gid)

    seasonNamePath = correctedFilePath.replace(plex_grab_folder + '/', '')
    seasonNamePath = seasonNamePath[0:seasonNamePath.find('/')]
    seasonNamePath = newShowPath + '/' + seasonNamePath
    if os.path.isdir(seasonNamePath) == False:
        os.mkdir(seasonNamePath)
        if change_owner == True:
            os.chown(seasonNamePath, change_owner_uid, change_owner_gid)
        
    newFileLocation = correctedFilePath.replace(plex_grab_folder, newShowPath)
    
    try:
        shutil.move(correctedFilePath, newFileLocation)
        if change_owner == True:
            os.chown(newFileLocation, change_owner_uid, change_owner_gid)
        sys.stdout.write("{}: Moved {} to folder {}\n".format(scriptName, correctedFilePath, newFileLocation))
    except Exception as e:
        sys.stderr.write("{}: Error moving file {}: {}.\n".format(scriptName, correctedFilePath, e))

if scriptEnabled == True:
    runScript = True
    if os.path.exists(conf_loc_path_file) == True:
        try:
            # Opening JSON file
            f = open(conf_loc_path_file, 'r')
            data = json.load(f)
            
            config = data['live_tv_move']
            plex_grab_folder = config['plex_grab_folder']
            move_to_folder = config['plex_library_folder']
            move_time_hours = config['move_time_hours']
            change_owner = config['enable_change_owner'] > 0
            if change_owner == True:
                if hasattr(os, 'chown') == True:
                    change_owner_uid = config['change_owner_uid']
                    change_owner_gid = config['change_owner_gid']
                else:
                    change_owner = False
                    sys.stdout.write("{}: LIVE_TV_CHANGE_OWNER set to TRUE but OS has no chown operation. Disabling Owner Change\n".format(scriptName))
            
        except Exception as e:
            sys.stderr.write("{}: ERROR Reading Config file {}\n".format(scriptName, e))
            runScript = False
    else:
        runScript = False
    
    if runScript == True:
        for file in glob.glob(plex_grab_folder + "/**/*", recursive=True):
            if file.endswith(".ts") or file.endswith(".mkv"):
                time_difference = datetime.now() - datetime.fromtimestamp(os.path.getmtime(file))
                hoursSincePlay = (time_difference.days * 24) + (time_difference.seconds / 3600)
                if hoursSincePlay >= move_time_hours:
                    move_file(file)
                else:
                    sys.stdout.write("{}: Pending Move. File modified {:.1f} hours ago will move at {} hours. {}\n".format(scriptName, hoursSincePlay, move_time_hours, file))
