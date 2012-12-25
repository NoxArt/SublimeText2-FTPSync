# -*- coding: utf-8 -*-

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
import datetime
import fnmatch
import re
import tempfile


# ==== Initialization and optimization =====================================================

# difference in time when comes to local vs remote {last modified} [s]
timeDifferenceTolerance = 1
# limit for breaking down a filepath structure when looking for config files
nestingLimit = 30
# bom marks (decimal)
bomMarks = {
    'utf8': [239,187,191],
    'utf16be': [254,255],
    'utf16le': [255,254],
    'utf32be': [0,0,254,255],
    'utf32le': [255,254,0,0],
    'utf7': [43,47,118,56,43,47,118,57,43,47,118,43,43,47,118,47],
    'utf1': [247,100,76],
    'utfebcdic': [221,115,102,115],
    'scsu': [14,254,255],
    'bocu-1': [251,238,40],
    'gb18030': [132,49,149,51]
}
bomMaxLength = 16
# file_path[string] => textual[boolean]
isTextCache = {}


# ==== Content =============================================================================

# A file representation with helper methods
class Metafile:

    def __init__(self, name, isDir, lastModified, filesize, path=None):
        self.name = name
        self.isDir = bool(isDir)
        self.lastModified = float(lastModified)
        self.filesize = float(filesize)
        self.path = path

    def getName(self):
        return self.name

    def getPath(self):
        return self.path

    def isDirectory(self):
        return self.isDir

    def getLastModified(self):
        return self.lastModified

    def getLastModifiedFormatted(self, format='%Y-%m-%d %H:%M'):
        return formatTimestamp(self.lastModified, format)

    def getFilesize(self):
        return self.filesize

    def isNewerThan(self, compared_file):
        if type(compared_file) is str or type(compared_file) is unicode:
            if os.path.exists(compared_file) is False:
                return False

            lastModified = os.path.getmtime(compared_file)
        elif isinstance(compared_file, Metafile):
            lastModified = compared_file.getLastModified()
        else:
            raise TypeError("Compared_file must be either string (file_path) or Metafile instance")

        return self.lastModified > lastModified

    def isDifferentSizeThan(self, compared_file):
        if type(compared_file) is str or type(compared_file) is unicode:
            if os.path.exists(compared_file) is False:
                return False

            lastModified = os.path.getsize(compared_file)
        elif isinstance(compared_file, Metafile):
            lastModified = compared_file.getLastModified()
        else:
            raise TypeError("Compared_file must be either string (file_path) or Metafile instance")

        return self.filesize != os.path.getsize(compared_file)



# Converts file_path to Metafile
#
# @type file_path: string
#
# @return Metafile
def fileToMetafile(file_path):
    name = os.path.basename(file_path)
    path = file_path
    isDir = os.path.isdir(file_path)
    lastModified = os.path.getmtime(file_path)
    filesize = os.path.getsize(file_path)

    return Metafile(name, isDir, lastModified, filesize, path)



# Returns a timestamp formatted for humans
#
# @type timestamp: int|float
# @type format: string
# @param format: see http://docs.python.org/library/time.html#time.strftime
#
# @return string
def formatTimestamp(timestamp, format='%Y-%m-%d %H:%M'):
    return datetime.datetime.fromtimestamp(int(timestamp)).strftime(format)


# Get all folders paths from given path upwards
#
# @type  file_path: string
# @param file_path: absolute file path to return the paths from
#
# @return list<string> of file paths
#
# @global nestingLimit
def getFolders(file_path):
    if file_path is None:
        return []

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
    if folders is None:
        return None

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
    if paths is None:
        return []

    files = []
    fileNames = []

    for target in paths:
        if target not in fileNames:
            fileNames.append(target)
            files.append([target, getConfigFile(target)])

    return files



# Goes through paths using glob and returns list of Metafiles
#
# @type pattern: string
# @param pattern: glob-like filename pattern
# @type root: string
# @param root: top searched directory
#
# @return list<Metafiles>
def gatherMetafiles(pattern, root):
    if pattern is None:
        return []

    result = {}
    file_names = []

    for subroot, dirnames, filenames in os.walk(root):
        for filename in fnmatch.filter(filenames, pattern):
            target = os.path.join(subroot, filename)

            if target not in file_names:
                file_names.append(target)
                result[target] = fileToMetafile(target)

        for folder in dirnames:
            result = dict(result.items() + gatherMetafiles(pattern, os.path.join(root, folder)).items())

    return result



# Returns difference using lastModified between file dicts
#
# @type metafilesBefore: dict
# @type metafilesAfter: dict
#
# @return list<Metafiles>
def getChangedFiles(metafilesBefore, metafilesAfter):
    changed = []
    for file_path in metafilesAfter:
        if file_path in metafilesBefore and metafilesAfter[file_path].isNewerThan(metafilesBefore[file_path]):
                changed.append(metafilesAfter[file_path])

    return changed



# Abstraction of os.rename for replacing cases
#
# @type source: string
# @param source: source file path
# @type destination: string
# @param destination: destination file path
def replace(source, destination):
    destinationTemp = destination + '.bak'
    try:
        os.rename(source, destination)
    except OSError:
        os.rename(destination, destinationTemp)

        try:
            os.rename(source, destination)
            os.unlink(destinationTemp)
        except OSError, e:
            os.rename(destinationTemp, destination)
            raise



# Performing operation on temporary file and replacing it back
#
# @type source: callback(file)
# @param source: operation performed on temporary file
def viaTempfile(file_path, operation):
    exceptionOccured = None
    directory = os.path.dirname(file_path)
    temp = tempfile.NamedTemporaryFile('wb', dir = directory, delete = False)

    try:
        operation(temp)
    except Exception, exp:
        exceptionOccured = exp
    finally:
        temp.flush()
        temp.close()

        if exceptionOccured is False:
            replace(temp.name, file_path)

        os.unlink(temp.name)

        if exceptionOccured is not None:
            raise exceptionOccured



# Guesses whether given file is textual or not
#
# @type file_path: string
# @type asciiWhitelist: None|list<string>
# @type binaryWhitelist: None|list<string>
#
# @return boolean whether it's likely textual or binary
def isTextFile(file_path, asciiWhitelist=None, binaryWhitelist=None):

    return False

    # check cache
    if file_path in isTextCache:
        return isTextCache[file_path]

    # check extension
    extension = os.path.splitext(file_path)[1][1:]

    if extension:

        if type(asciiWhitelist) is list:
            if extension in asciiWhitelist:
                isTextCache[file_path] = True
                return True

        if type(binaryWhitelist) is list:
            if extension in binaryWhitelist:
                isTextCache[file_path] = False
                return False

    # check BOM
    f = open(file_path, 'rb')
    beginning = f.read(bomMaxLength)
    f.close()

    begin = []
    for char in beginning:
        begin.append(ord(char))

    for encoding in bomMarks:
        subarray = begin[0:len(bomMarks[encoding])]

        if subarray == begin:
            isTextCache[file_path] = True
            return True

    # is not
    isTextCache[file_path] = False
    return False