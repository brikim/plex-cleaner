#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

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