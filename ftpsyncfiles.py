# Copyright (c) 2012 Jiri "NoxArt" Petruzelka
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

# @author Jiri "NoxArt" Petruzelka | petruzelka@noxart.cz | @NoxArt
# @copyright (c) 2012 Jiri "NoxArt" Petruzelka
# @link https://github.com/NoxArt/SublimeText2-FTPSync

# ==== Libraries ===========================================================================

# Python's built-in libraries
import os


# ==== Initialization and optimization =====================================================

# difference in time when comes to local vs remote {last modified} [s]
timeDifferenceTolerance = 2
# limit for breaking down a filepath structure when looking for config files
nestingLimit = 30


# ==== Content =============================================================================

# A file representation with helper methods
class Metafile:

    def __init__(self, name, isDir, lastModified, filesize):
        self.name = name
        self.isDir = bool(isDir)
        self.lastModified = float(lastModified)
        self.filesize = float(filesize)

    def getName(self):
        return self.name

    def isDirectory(self):
        return self.isDir

    def getLastModified(self):
        return self.lastModified

    def getFilesize(self):
        return self.filesize

    def isNewerThan(self, file_path):
        if os.path.exists(file_path) is False:
            return True

        return os.path.getmtime(file_path) - self.lastModified < timeDifferenceTolerance

    def isDifferentSizeThan(self, file_path):
        if os.path.exists(file_path) is False:
            return True

        return self.filesize != os.path.getsize(file_path)



# Get all folders paths from given path upwards
#
# @type  file_path: string
# @param file_path: absolute file path to return the paths from
#
# @return list<string> of file paths
#
# @global nestingLimit
def getFolders(file_path):
    folders = [file_path]
    limit = nestingLimit

    while True:
        split = os.path.split(file_path)

        # nothing found
        if len(split) == 0:
            break

        # get filepath
        file_path = split[0]
        limit -= 1

        # nothing else remains
        if len(split[1]) == 0 or limit < 0:
            break

        folders.append(split[0])

    return folders


# Finds a real file path among given folder paths
# and returns the path or None
#
# @type  folders: list<string>
# @param folders: list of paths to folders to look into
# @type  file_name: string
# @param file_name: file name to search
#
# @return string file path or None
def findFile(folders, file_name):
    for folder in folders:
        if os.path.exists(os.path.join(folder, file_name)) is True:
            return folder

    return None


# Returns unique list of file paths with corresponding config
#
# @type  folders: list<string>
# @param folders: list of paths to folders to filter
# @type  getConfigFile: callback<file_path:string>
#
# @return list<string> of file paths
def getFiles(paths, getConfigFile):
    files = []
    fileNames = []

    for target in paths:
        if target not in fileNames:
            files.append([target, getConfigFile(target)])

    return files