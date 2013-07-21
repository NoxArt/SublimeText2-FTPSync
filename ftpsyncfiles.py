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
import sys


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
# permission triples
triples = {
	'---': 0,
	'--x': 1,
	'--s': 1,
	'--t': 1,
	'-w-': 2,
	'-wx': 3,
	'-ws': 3,
	'-wt': 3,
	'r--': 4,
	'r-x': 5,
	'r-s': 5,
	'r-t': 5,
	'rw-': 6,
	'rwx': 7,
	'rws': 7,
	'rwt': 7,
}



# ==== Content =============================================================================

# Returns whether the variable is some form os string
def isString(var):
	var_type = type(var)

	if sys.version[0] == '3':
		return var_type is str or var_type is bytes
	else:
		return var_type is str or var_type is unicode

# A file representation with helper methods
class Metafile:

	def __init__(self, name, isDir, lastModified, filesize, path=None, permissions=None):
		self.name = name
		self.isDir = bool(isDir)
		self.lastModified = lastModified
		if self.lastModified is not None:
			self.lastModified = float(self.lastModified)

		self.filesize = filesize
		if self.filesize is not None:
			self.filesize = float(self.filesize)

		self.path = path
		self.permissions = permissions

	def getName(self):
		return self.name

	def getPath(self):
		return self.path

	def getPermissions(self):
		return self.permissions

	def getPermissionsNumeric(self):
		symbolic = self.permissions

		numeric  = "0"
		numeric += str(triples[symbolic[0:3]])
		numeric += str(triples[symbolic[3:6]])
		numeric += str(triples[symbolic[6:9]])

		return numeric

	def isDirectory(self):
		return self.isDir

	def getLastModified(self):
		return self.lastModified

	def getLastModifiedFormatted(self, format='%Y-%m-%d %H:%M'):
		return formatTimestamp(self.lastModified, format)

	def getFilesize(self):
		return self.filesize

	def isSameFilepath(self, filepath):
		return os.path.realpath(self.getPath()) == os.path.realpath(filepath)

	def isNewerThan(self, compared_file):
		if self.lastModified is None:
			return False

		if isString(compared_file):
			if os.path.exists(compared_file) is False:
				return False

			lastModified = os.path.getmtime(compared_file)
		elif isinstance(compared_file, Metafile):
			lastModified = compared_file.getLastModified()
		else:
			raise TypeError("Compared_file must be either string (file_path) or Metafile instance")

		return self.lastModified > lastModified

	def isDifferentSizeThan(self, compared_file):
		if self.filesize is None:
			return False

		if isString(compared_file):
			if os.path.exists(compared_file) is False:
				return False

			lastModified = os.path.getsize(compared_file)
		elif isinstance(compared_file, Metafile):
			lastModified = compared_file.getLastModified()
		else:
			raise TypeError("Compared_file must be either string (file_path) or Metafile instance")

		return self.filesize != os.path.getsize(compared_file)



# Detects if object is a string and if so converts to unicode, if not already
#
# @source http://farmdev.com/talks/unicode/
# @author Ivan Krstić
def to_unicode_or_bust(obj, encoding='utf-8'):
	if isinstance(obj, basestring):
		if not isinstance(obj, unicode):
			obj = unicode(obj, encoding)
	return obj



# Converts file_path to Metafile
#
# @type file_path: string
#
# @return Metafile
def fileToMetafile(file_path):
	if type(file_path) is str:
		file_path = file_path.encode('utf-8')
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
	if timestamp is None:
		return "-"

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
		if type(folder) is not str:
			folder = folder.decode('utf-8')

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
			files.append([target.encode('utf-8'), getConfigFile(target.encode('utf-8'))])

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
			target = os.path.join(subroot, filename).encode('utf-8')

			if target not in file_names:
				file_names.append(target)
				result[target] = fileToMetafile(target)

		for folder in dirnames:
			result.update(gatherMetafiles(pattern, os.path.join(root, folder)).items())

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
		if hasattr(file_path, 'encode'):
			file_path = file_path.encode('utf-8')

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
	destinationTemp = destination + '.ftpsync.bak'
	try:
		os.rename(source, destination)
	except OSError:
		os.rename(destination, destinationTemp)

		try:
			os.rename(source, destination)
			os.unlink(destinationTemp)
		except OSError as e:
			os.rename(destinationTemp, destination)
			raise



# Performing operation on temporary file and replacing it back
#
# @type operation: callback(file)
# @param operation: operation performed on temporary file
# @type permissions: int (octal)
# @type mode: string
# @param mode: file opening mode
def viaTempfile(file_path, operation, permissions, mode):
	if permissions is None:
		permissions = '0755'
	exceptionOccured = None

	if sys.version[0] == '3':
		directory = os.path.dirname(file_path)
	else:
		directory = os.path.dirname(file_path.encode('utf-8'))

	if os.path.exists(directory) is False:
		os.makedirs(directory, int(permissions, 8))

	temp = tempfile.NamedTemporaryFile(mode, suffix = '.ftpsync.temp', dir = directory, delete = False)

	try:
		operation(temp)
	except Exception as exp:
		exceptionOccured = exp
	finally:
		temp.flush()
		temp.close()

		if exceptionOccured is None:
			if os.path.exists(file_path) is False:
				created = open(file_path, 'w+')
				created.close()

			replace(temp.name, file_path)

		if os.path.exists(temp.name):
			os.unlink(temp.name)

		if exceptionOccured is not None:
			raise exceptionOccured



# Guesses whether given file is textual or not
#
# @type file_path: string
# @type asciiWhitelist: list<string>
#
# @return boolean whether it's likely textual or binary
def isTextFile(file_path, asciiWhitelist):
    fileName, fileExtension = os.path.splitext(file_path)

    if fileExtension and fileExtension[1:] in asciiWhitelist:
        return True

    return False



# Adds . and .. entries if missing in the collection
#
# @type contents: list<Metadata>
#
# @return list<metadata>
def addLinks(contents):
	hasSelf = False
	hasUp = False
	single = None

	for entry in contents:
		if entry.getName() == '.':
			hasSelf = True
		elif entry.getName() == '..':
			hasUp = True

		if hasSelf and hasUp:
			return contents
		else:
			single = entry

	if single is not None:
		if hasSelf == False:
			entrySelf = Metafile('.', True, None, None, single.getPath(), None)
			contents.append(entrySelf)

		if hasUp == False:
			entryUp = Metafile('..', True, None, None, single.getPath(), None)
			contents.append(entryUp)

	return contents
