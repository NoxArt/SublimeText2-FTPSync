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

# Doc comment syntax inspired by http://stackoverflow.com/a/487203/387503

# ==== Libraries ===========================================================================

# Sublime Text 2 API: see http://www.sublimetext.com/docs/2/api_reference.html
# Sublime Text 3 API: see http://www.sublimetext.com/docs/3/api_reference.html
import sublime
import sublime_plugin

# Python's built-in libraries
import copy
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import traceback
import webbrowser

# FTPSync libraries
if sys.version < '3':
	from lib2.minify_json import json_minify

	from ftpsynccommon import Types
	from ftpsyncwrapper import CreateConnection, TargetAlreadyExists
	from ftpsyncprogress import Progress
	from ftpsyncfiles import getFolders, findFile, getFiles, formatTimestamp, gatherMetafiles, replace, addLinks, fileToMetafile
	from ftpsyncworker import Worker
	from ftpsyncfilewatcher import FileWatcher
	# exceptions
	from ftpsyncexceptions import FileNotFoundException
else:
	from FTPSync.lib3.minify_json import json_minify

	from FTPSync.ftpsynccommon import Types
	from FTPSync.ftpsyncwrapper import CreateConnection, TargetAlreadyExists
	from FTPSync.ftpsyncprogress import Progress
	from FTPSync.ftpsyncfiles import getFolders, findFile, getFiles, formatTimestamp, gatherMetafiles, replace, addLinks, fileToMetafile
	from FTPSync.ftpsyncworker import Worker
	from FTPSync.ftpsyncfilewatcher import FileWatcher
	# exceptions
	from FTPSync.ftpsyncexceptions import FileNotFoundException

# ==== Initialization and optimization =====================================================
__dir__ = os.path.dirname(os.path.realpath(__file__))

isLoaded = False

isDebug = True
# print overly informative messages?
isDebugVerbose = True
# default config for a project
projectDefaults = {}
nested = []
index = 0
# global config key - for specifying global config in settings file
globalConfigKey = '__global'
ignore = False
# time format settings
timeFormat = ""
# delay before check of right opened file is performed, cancelled if closed in the meantime
downloadOnOpenDelay = 0

coreConfig = {}


# name of a file to be detected in the project
configName = 'ftpsync.settings'
# name of a file that is a default sheet for new configs for projects
connectionDefaultsFilename = 'ftpsync.default-settings'
# timeout for a Sublime status bar messages [ms]
messageTimeout = 250
# comment removing regexp
removeLineComment = re.compile('//.*', re.I)
# deprecated names
deprecatedNames = {
	"check_time": "overwrite_newer_prevention"
}


# connection cache pool - all connections
connections = {}
# connections currently marked as {in use}
usingConnections = []
# root check cache
rootCheckCache = {}
# individual folder config cache, file => config path
configs = {}
# scheduled delayed uploads, file_path => action id
scheduledUploads = {}
# limit of workers
workerLimit = 0
# debug workers?
debugWorkers = False
# debug json?
debugJson = False


# overwrite cancelled
overwriteCancelled = []

# last navigation
navigateLast = {
	'config_file': None,
	'connection_name': None,
	'path': None
}
displayDetails = False
displayPermissions = False
displayTimestampFormat = False

# last folder
re_thisFolder = re.compile("/([^/]*?)/?$", re.I)
re_parentFolder = re.compile("/([^/]*?)/[^/]*?/?$", re.I)

# watch pre-scan
preScan = {}

# temporarily remembered passwords
#
# { settings_filepath => { connection_name => password }, ... }
passwords = {}

# Overriding config for on-the-fly modifications
overridingConfig = {}

def isString(var):
	var_type = type(var)

	if sys.version[0] == '3':
		return var_type is str or var_type is bytes
	else:
		return var_type is str or var_type is unicode

def plugin_loaded():
	global coreConfig
	global debugJson
	global debugWorkers
	global displayDetails
	global displayPermissions
	global displayTimestampFormat
	global downloadOnOpenDelay
	global ignore
	global index
	global isDebug
	global isDebugVerbose
	global isLoaded
	global nested
	global projectDefaults
	global re_ignore
	global settings
	global systemNotifications
	global timeFormat
	global workerLimit

	# global config
	settings = sublime.load_settings('FTPSync.sublime-settings')

	# test settings
	if settings.get('project_defaults') is None:
		print ("="*86)
		print ("FTPSync > Error loading settings ... please restart Sublime Text after installation")
		print ("="*86)

	# print debug messages to console?
	isDebug = settings.get('debug')
	# print overly informative messages?
	isDebugVerbose = settings.get('debug_verbose')
	# default config for a project
	projectDefaults = settings.get('project_defaults')

	index = 0

	for item in projectDefaults.items():
		if type(item[1]) is dict:
			nested.append(index)
		index += 1

	# global ignore pattern
	ignore = settings.get('ignore')
	# time format settings
	timeFormat = settings.get('time_format')
	# delay before check of right opened file is performed, cancelled if closed in the meantime
	downloadOnOpenDelay = settings.get('download_on_open_delay')
	# system notifications
	systemNotifications = settings.get('system_notifications')

	# compiled global ignore pattern
	if isString(ignore):
		re_ignore = re.compile(ignore)
	else:
		re_ignore = None

	# loaded project's config will be merged with this global one
	coreConfig = {
		'ignore': ignore,
		'debug_verbose': settings.get('debug_verbose'),
		'ftp_retry_limit': settings.get('ftp_retry_limit'),
		'ftp_retry_delay': settings.get('ftp_retry_delay'),
		'connection_timeout': settings.get('connection_timeout'),
		'ascii_extensions': settings.get('ascii_extensions'),
		'binary_extensions': settings.get('binary_extensions')
	}

	# limit of workers
	workerLimit = settings.get('max_threads')
	# debug workers?
	debugWorkers = settings.get('debug_threads')
	# debug json?
	debugJson = settings.get('debug_json')

	# browsing
	displayDetails = settings.get('browse_display_details')
	displayPermissions = settings.get('browse_display_permission')
	displayTimestampFormat = settings.get('browse_timestamp_format')



	isLoaded = True
	if isDebug:
		print ('FTPSync > plugin async loaded')

if int(sublime.version()) < 3000:
	plugin_loaded()

# ==== Generic =============================================================================

# Returns file with syntax for settings file
def getConfigSyntax():
	if packageExists('AAAPackageDev/Syntax Definitions/Sublime Settings.tmLanguage'):
		return 'Packages/AAAPackageDev/Syntax Definitions/Sublime Settings.tmLanguage'
	else:
		return 'Packages/JavaScript/JSON.tmLanguage'

# Returns if Sublime has currently active View
#
# ST3 on no opened view returns a View with empty file_name (wtf)
#
# @return boolean
def hasActiveView():
	window = sublime.active_window()
	if window is None:
		return False

	view = window.active_view()
	if view is None or view.file_name() is None:
		return False
	return True

# Dumps the exception to console
def handleException(exception):
	print ("FTPSync > Exception in user code:")
	print ('-' * 60)
	traceback.print_exc(file=sys.stdout)
	print ('-' * 60)


# Safer print of exception message
def stringifyException(exception):
	return str(exception)


# Checks whether cerain package exists
def packageExists(packageName):
	return os.path.exists(os.path.join(sublime.packages_path(), packageName))


def decode(string):
	if hasattr('x', 'decode') and callable(getattr('x', 'decode')):
		return string.decode('utf-8')
	else:
		return string


# ==== Messaging ===========================================================================

# Shows a message into Sublime's status bar
#
# @type  text: string
# @param text: message to status bar
def statusMessage(text):
	sublime.status_message(text)


# Schedules a single message to be logged/shown
#
# @type  text: string
# @param text: message to status bar
#
# @global messageTimeout
def dumpMessage(text):
	sublime.set_timeout(lambda: statusMessage(text), messageTimeout)


# Prints a special message to console and optionally to status bar
#
# @type  text: string
# @param text: message to status bar
# @type  name: string|None
# @param name: comma-separated list of connections or other auxiliary info
# @type  onlyVerbose: boolean
# @param onlyVerbose: print only if config has debug_verbose enabled
# @type  status: boolean
# @param status: show in status bar as well = true
#
# @global isDebug
# @global isDebugVerbose
def printMessage(text, name=None, onlyVerbose=False, status=False):
	message = "FTPSync"

	if name is not None:
		message += " [" + name + "]"

	message += " > "
	message += text

	if isDebug and (onlyVerbose is False or isDebugVerbose is True):
		print (message.encode('utf-8'))

	if status:
		dumpMessage(message)


# Issues a system notification for certian event
#
# @type text: string
# @param text: notification message
def systemNotify(text):
	try:
		import subprocess

		text = "FTPSync > " + text

		if sys.platform == "darwin":
			""" Run Grown Notification """
			cmd = '/usr/local/bin/growlnotify -a "Sublime Text 2" -t "FTPSync message" -m "'+text+'"'
			subprocess.call(cmd,shell=True)
		elif sys.platform == "linux2":
			subprocess.call('/usr/bin/notify-send "Sublime Text 2" "'+text+'"',shell=True)
		elif sys.platform == "win32":
			""" Find the notifaction platform for windows if there is one"""

	except Exception as e:
		printMessage("Notification failed")
		handleExceptions(e)


# Creates a process message with progress bar (to be used in status bar)
#
# @type  stored: list<string>
# @param stored: usually list of connection names
# @type progress: Progress
# @type action: string
# @type action: action that the message reports about ("uploaded", "downloaded"...)
# @type  basename: string
# @param basename: name of a file connected with the action
#
# @return string message
def getProgressMessage(stored, progress, action, basename = None):
	base = "FTPSync [remotes: " + ",".join(stored) + "] "
	action = "> " + action + " "

	if progress is not None:
		base += " ["

		percent = progress.getPercent()

		for i in range(0, int(percent)):
			base += "="
		for i in range(int(percent), 20):
			base += "--"

		base += " " + str(progress.current) + "/" + str(progress.getTotal()) + "] "

	base += action

	if basename is not None:
		base += " {" + basename + "}"

	return base


# ==== Config =============================================================================

# Alters override config
#
# @type  config_dir_name: string
# @param config_dir_name: path to a folder of a config
# @type  property: string
# @param property: property to be modified
# @type value: mixed
# @type specificName: string
# @param specificName: use to only modify specific connection's value
#
# @global overrideConfig
def overrideConfig(config_file_path, property, value, specificName=None):
	if config_file_path is None or os.path.exists(config_file_path) is False:
		return

	config = loadConfig(config_file_path)

	if config_file_path not in overridingConfig:
		overridingConfig[config_file_path] = { 'connections': {} }

	for name in config['connections']:
		if specificName and name != specificName:
			continue

		if name not in overridingConfig[config_file_path]['connections']:
			overridingConfig[config_file_path]['connections'][name] = {}

		overridingConfig[config_file_path]['connections'][name][property] = value


# Invalidates all config cache entries belonging to a certain directory
# as long as they're empty or less nested in the filesystem
#
# @type  config_dir_name: string
# @param config_dir_name: path to a folder of a config to be invalidated
#
# @global configs
def invalidateConfigCache(config_dir_name):
	for file_path in configs:
		if file_path.startswith(config_dir_name) and (configs[file_path] is None or config_dir_name.startswith(configs[file_path])):
			configs.remove(configs[file_path])


# Finds a config file in given folders
#
# @type  folders: list<string>
# @param folders: list of paths to folders to filter
#
# @return list<string> of file paths
#
# @global configName
def findConfigFile(folders):
	return findFile(folders, configName)


# Returns first found config file from folders
#
# @type  folders: list<string>
# @param folders: list of paths to folders to search in
#
# @return config filepath
def guessConfigFile(folders):
	for folder in folders:
		config = getConfigFile(folder)
		if config is not None:
			return config

		for folder in os.walk(folder):
			config = getConfigFile(folder[0])
			if config is not None:
				return config

	return None


# Returns configuration file for a given file
#
# @type  file_path: string
# @param file_path: file_path to the file for which we try to find a config
#
# @return file path to the config file or None
#
# @global configs
def getConfigFile(file_path):
	cacheKey = file_path
	if isString(cacheKey) is False:
		cacheKey = cacheKey.decode('utf-8')

	# try cached
	try:
		if configs[cacheKey]:
			printMessage("Loading config: cache hit (key: " + cacheKey + ")")

		return configs[cacheKey]

	# cache miss
	except KeyError:
		try:
			folders = getFolders(file_path)

			if folders is None or len(folders) == 0:
				return None

			configFolder = findConfigFile(folders)

			if configFolder is None:
				printMessage("Found no config for {" + cacheKey + "}", None, True)
				return None

			config = os.path.join(configFolder, configName)
			configs[cacheKey] = config
			return config

		except AttributeError:
			return None


# Returns hash of file_path
#
# @type  file_path: string
# @param file_path: file path to the file of which we want the hash
#
# @return hash of filepath
def getFilepathHash(file_path):
	return hashlib.md5(file_path.encode('utf-8')).hexdigest()


# Returns path of file from its config file
#
# @type  file_path: string
# @param file_path: file path to the file of which we want the hash
#
# @return string file path from settings root
def getRootPath(file_path, prefix = ''):
	return prefix + os.path.relpath(file_path, os.path.dirname(getConfigFile(file_path))).replace('\\', '/')


# Returns a file path associated with view
#
# @type  file_path: string
# @param file_path: file path to the file of which we want the hash
#
# @return string file path
def getFileName(view):
	return view.file_name()


# Gathers all entries from selected paths
#
# @type  file_path: list<string>
# @param file_path: list of file/folder paths
#
# @return list of file/folder paths
def gatherFiles(paths):
	syncFiles = []
	fileNames = []

	for target in paths:
		if os.path.isfile(target):
			if target not in fileNames:
				fileNames.append(target)
				syncFiles.append([target, getConfigFile(target)])
		elif os.path.isdir(target):
			empty = True

			for root, dirs, files in os.walk(target):
				for file_path in files:
					empty = False

					if file_path not in fileNames:
						fileNames.append(target)
						syncFiles.append([os.path.join(root, file_path), getConfigFile(os.path.join(root, file_path))])

				for folder in dirs:
					path = os.path.join(root, folder)

					if not os.listdir(path) and path not in fileNames:
						fileNames.append(path)
						syncFiles.append([path, getConfigFile(path)])


			if empty is True:
				syncFiles.append([target, getConfigFile(target)])

	return syncFiles


# Returns hash of configuration contents
#
# @type config: dict
#
# @return string
#
# @link http://stackoverflow.com/a/8714242/387503
def getObjectHash(o):
	if isinstance(o, set) or isinstance(o, tuple) or isinstance(o, list):
		return tuple([getObjectHash(e) for e in o])
	elif not isinstance(o, dict):
		return hash(o)

	new_o = copy.deepcopy(o)
	for k, v in new_o.items():
		new_o[k] = getObjectHash(v)

	return hash(tuple(frozenset(new_o.items())))


# Updates deprecated config to newer version
#
# @type config: dict
#
# @return dict (config)
#
# @global deprecatedNames
def updateConfig(config):
	for old_name in deprecatedNames:
		new_name = deprecatedNames[old_name]

		if new_name in config:
			config[old_name] = config[new_name]
		elif old_name in config:
			config[new_name] = config[old_name]

	return config


# Verifies contents of a given config object
#
# Checks that it's an object with all needed keys of a proper type
# Does not check semantic validity of the content
#
# Should be used on configs merged with the defaults
#
# @type  config: dict
# @param config: config dict
#
# @return string verification fail reason or a boolean
def verifyConfig(config):
	if type(config) is not dict:
		return "Config is not a {dict} type"

	keys = ["username", "password", "private_key", "private_key_pass", "path", "encoding", "tls", "use_tempfile", "upload_on_save", "port", "timeout", "ignore", "check_time", "download_on_open", "upload_delay", "after_save_watch", "time_offset", "set_remote_lastmodified", "default_folder_permissions", "default_local_permissions", "always_sync_local_permissions"]

	for key in keys:
		if key not in config:
			return "Config is missing a {" + key + "} key"

	if config['username'] is not None and isString(config['username']) is False:
		return "Config entry 'username' must be null or string, " + str(type(config['username'])) + " given"

	if config['password'] is not None and isString(config['password']) is False:
		return "Config entry 'password' must be null or string, " + str(type(config['password'])) + " given"

	if config['private_key'] is not None and isString(config['private_key']) is False:
		return "Config entry 'private_key' must be null or string, " + str(type(config['private_key'])) + " given"

	if config['private_key_pass'] is not None and isString(config['private_key_pass']) is False:
		return "Config entry 'private_key_pass' must be null or string, " + str(type(config['private_key_pass'])) + " given"

	if config['ignore'] is not None and isString(config['ignore']) is False:
		return "Config entry 'ignore' must be null or string, " + str(type(config['ignore'])) + " given"

	if isString(config['path']) is False:
		return "Config entry 'path' must be a string, " + str(type(config['path'])) + " given"

	if config['encoding'] is not None and isString(config['encoding']) is False:
		return "Config entry 'encoding' must be a string, " + str(type(config['encoding'])) + " given"

	if type(config['tls']) is not bool:
		return "Config entry 'tls' must be true or false, " + str(type(config['tls'])) + " given"

	if type(config['passive']) is not bool:
		return "Config entry 'passive' must be true or false, " + str(type(config['passive'])) + " given"

	if type(config['use_tempfile']) is not bool:
		return "Config entry 'use_tempfile' must be true or false, " + str(type(config['use_tempfile'])) + " given"

	if type(config['set_remote_lastmodified']) is not bool:
		return "Config entry 'set_remote_lastmodified' must be true or false, " + str(type(config['set_remote_lastmodified'])) + " given"

	if type(config['upload_on_save']) is not bool:
		return "Config entry 'upload_on_save' must be true or false, " + str(type(config['upload_on_save'])) + " given"

	if type(config['check_time']) is not bool:
		return "Config entry 'check_time' must be true or false, " + str(type(config['check_time'])) + " given"

	if type(config['download_on_open']) is not bool:
		return "Config entry 'download_on_open' must be true or false, " + str(type(config['download_on_open'])) + " given"

	if type(config['upload_delay']) is not int and type(config['upload_delay']) is not long:
		return "Config entry 'upload_delay' must be integer or long, " + str(type(config['upload_delay'])) + " given"

	if config['after_save_watch'] is not None and type(config['after_save_watch']) is not list:
		return "Config entry 'after_save_watch' must be null or list, " + str(type(config['after_save_watch'])) + " given"

	if type(config['port']) is not int and type(config['port']) is not long:
		return "Config entry 'port' must be an integer or long, " + str(type(config['port'])) + " given"

	if type(config['timeout']) is not int and type(config['timeout']) is not long:
		return "Config entry 'timeout' must be an integer or long, " + str(type(config['timeout'])) + " given"

	if type(config['time_offset']) is not int and type(config['time_offset']) is not long:
		return "Config entry 'time_offset' must be an integer or long, " + str(type(config['time_offset'])) + " given"

	return True


# Parses JSON-type file with comments stripped out (not part of a proper JSON, see http://json.org/)
#
# @type  file_path: string
#
# @return dict
#
# @global removeLineComment
def parseJson(file_path):
	contents = ""

	try:
		file = open(file_path, 'r')

		for line in file:
			contents += removeLineComment.sub('', line)
	finally:
		file.close()

	if debugJson:
		printMessage("Debug JSON:")
		print ("="*86)
		print (contents)
		print ("="*86)

	return json.loads(contents)


# Asks for passwords if missing in configuration
#
# @type config_file_path: string
# @type config: dict
# @param config: configuration object
# @type callback: callback
# @param callback: what should be done after config is filled
# @type window: Window
# @param window: SublimeText2 API Window object
#
# @global passwords
def addPasswords(config_file_path, config, callback, window):
	def setPassword(config, name, password):
		config['connections'][name]['password'] = password

		if config_file_path not in passwords:
			passwords[config_file_path] = {}

		passwords[config_file_path][name] = password

		addPasswords(config_file_path, config, callback, window)

	def ask(connectionName, host, username):
		window.show_input_panel('FTPSync > please provide password for:  ' + str(host) + ' ~ ' + str(username), "", lambda password: setPassword(config, connectionName, password), None, None)

	if type(config) is dict:
		for name in config['connections']:
			prop = config['connections'][name]

			if prop['password'] is None:
				if config_file_path in passwords and name in passwords[config_file_path] and passwords[config_file_path][name] is not None:
					config['connections'][name]['password'] = passwords[config_file_path][name]
				else:
					ask(name, prop['host'], prop['username'])
					return

	return callback()


# Fills passwords if missing in configuration
#
# @type fileList: [ [ filepath, config_file_path ], ... ]
# @type callback: callback
# @param callback: what should be done after config is filled
# @type window: Window
# @param window: SublimeText2 API Window object
#
# @global passwords
def fillPasswords(fileList, callback, window, index = 0):
	def ask():
		fillPasswords(fileList, callback, window, index + 1)

	i = 0
	length = len(fileList)

	if index >= length:
		callback(fileList)
		return

	config_files = []
	for filepath, config_file_path in fileList:
		if config_file_path not in config_files:
			config_files.append(config_file_path)

	for config_file_path in config_files:
		if i < index:
			i = i + 1
			continue

		if config_file_path is None:
			continue

		config = loadConfig(config_file_path)
		if config is not None:
			addPasswords(config_file_path, config, ask, window)
		return

	callback(fileList)


# Parses given config and adds default values to each connection entry
#
# @type  file_path: string
# @param file_path: file path to the file of which we want the hash
#
# @return config dict or None
#
# @global isLoaded
# @global coreConfig
# @global projectDefaults
def loadConfig(file_path):

	if isLoaded is False:
		printMessage("Settings not loaded (just installed?), please restart Sublime Text")
		return None

	if isString(file_path) is False:
		printMessage("LoadConfig expects string, " + str(type(file_path)) + " given")
		return None

	if os.path.exists(file_path) is False:
		return None

	# parse config
	try:
		config = parseJson(file_path)
	except Exception as e:
		printMessage("Failed parsing configuration file: {" + file_path + "} (commas problem?) [Exception: " + stringifyException(e) + "]", status=True)
		handleException(e)
		return None

	result = {}

	# merge with defaults and check
	for name in config:
		if type(config[name]) is not dict:
			printMessage("Failed using configuration: contents are not dictionaries but values", status=True)
			return None

		result[name] = dict(list(projectDefaults.items()) + list(config[name].items()))
		result[name]['file_path'] = file_path

		# fix path
		if len(result[name]['path']) > 1 and result[name]['path'][-1] != "/":
			result[name]['path'] = result[name]['path'] + "/"

		# merge nested
		for index in nested:
			list1 = list(list(projectDefaults.items())[index][1].items())
			list2 = list(result[name][list(projectDefaults.items())[index][0]].items())

			result[name][list(projectDefaults.items())[index][0]] = dict(list1 + list2)
		try:
			if result[name]['debug_extras']['dump_config_load'] is True:
				print(result[name])
		except KeyError:
			pass

		# add passwords
		if file_path in passwords and name in passwords[file_path] and passwords[file_path][name] is not None:
			result[name]['password'] = passwords[file_path][name]

		result[name] = updateConfig(result[name])

		verification_result = verifyConfig(result[name])

		if verification_result is not True:
			printMessage("Invalid configuration loaded: <" + str(verification_result) + ">", status=True)

	# merge with generics
	final = dict(list(coreConfig.items()) + list({"connections": result}.items()))

	# override by overridingConfig
	if file_path in overridingConfig:
		for name in overridingConfig[file_path]['connections']:
			if name in final['connections']:
				for item in overridingConfig[file_path]['connections'][name]:
					final['connections'][name][item] = overridingConfig[file_path]['connections'][name][item]

	return final


# ==== Remote =============================================================================

# Creates a new connection
#
# @type  config: object
# @param config: configuration object
# @type  hash: string
# @param hash: connection cache hash (config filepath hash actually)
#
# @return list of descendants of AbstractConnection (ftpsyncwrapper.py)
def makeConnection(config, hash=None, handleExceptions=True):

	result = []

	# for each config
	for name in config['connections']:
		properties = config['connections'][name]

		# 1. initialize
		try:
			connection = CreateConnection(config, name)
		except Exception as e:
			if handleExceptions is False:
				raise

			printMessage("Connection initialization failed [Exception: " + stringifyException(e) + "]", name, status=True)
			handleException(e)

			return []

		# 2. connect
		try:
			connection.connect()
		except Exception as e:
			if handleExceptions is False:
				raise

			printMessage("Connection failed [Exception: " + stringifyException(e) + "]", name, status=True)
			connection.close(connections, hash)
			handleException(e)

			return []

		printMessage("Connected to: " + properties['host'] + ":" + str(properties['port']) + " (timeout: " + str(properties['timeout']) + ") (key: " + str(hash) + ")", name)

		# 3. authenticate
		try:
			if connection.authenticate():
				printMessage("Authentication processed", name)
		except Exception as e:
			if handleExceptions is False:
				raise

			printMessage("Authentication failed [Exception: " + stringifyException(e) + "]", name, status=True)
			handleException(e)

			return []

		# 4. login
		if properties['username'] is not None and properties['password'] is not None:
			try:
				connection.login()
			except Exception as e:
				printMessage("Login failed [Exception: " + stringifyException(e) + "]", name, status=True)
				handleException(e)

				if properties['file_path'] in passwords and name in passwords[properties['file_path']]:
					passwords[properties['file_path']][name] = None

				if handleExceptions is False:
					raise

				return []

			pass_present = " (using password: NO)"
			if len(properties['password']) > 0:
				pass_present = " (using password: YES)"

			printMessage("Logged in as: " + properties['username'] + pass_present, name)
		else:
			printMessage("Anonymous connection", name)

		# 5. ensure that root exists
		cacheKey = properties['host'] + ":" + properties['path']
		if cacheKey not in rootCheckCache:
			try:
				connection.ensureRoot()

				rootCheckCache[cacheKey] = True
			except Exception as e:
				if handleExceptions is False:
					raise

				printMessage("Failed ensure root exists [Exception: " + stringifyException(e) + "]", name)
				handleException(e)

				return []

		# 6. set initial directory, set name, store connection
		try:
			connection.cwd(properties['path'])
		except Exception as e:
			if handleExceptions is False:
				raise

			printMessage("Failed to set path (probably connection failed) [Exception: " + stringifyException(e) + "]", name)
			handleException(e)

			return []

		# 7. add to connections list
		present = False
		for con in result:
			if con.name == connection.name:
				present = True

		if present is False:
			result.append(connection)

	return result


# Returns connection, connects if needed
#
# @type  hash: string
# @param hash: connection cache hash (config filepath hash actually)
# @type  config: object
# @param config: configuration object
# @type  shared: bool
# @param shared: whether to use shared connection
#
# @return list of descendants of AbstractConnection (ftpsyncwrapper.py)
#
# @global connections
def getConnection(hash, config, shared=True):
	if shared is False:
		return makeConnection(config, hash)

	# try cache
	try:
		if connections[hash] and len(connections[hash]) > 0:
			printMessage("Connection cache hit (key: " + hash + ")", None, True)

		if type(connections[hash]) is not list or len(connections[hash]) < len(config['connections']):
			raise KeyError

		# has config changed?
		valid = True
		index = 0
		for name in config['connections']:
			if getObjectHash(connections[hash][index].config) != getObjectHash(config['connections'][name]):
				valid = False

			index += 1

		if valid == False:
			for connection in connections[hash]:
				connection.close(connections, hash)

			raise KeyError

		# is config truly alive
		for connection in connections[hash]:
			if connection.isAlive() is False:
				raise KeyError

		return connections[hash]

	# cache miss
	except KeyError:
		connections[hash] = makeConnection(config, hash)

		# schedule connection timeout
		def closeThisConnection():
			if hash not in usingConnections:
				closeConnection(hash)
			else:
				sublime.set_timeout(closeThisConnection, config['connection_timeout'] * 1000)

		sublime.set_timeout(closeThisConnection, config['connection_timeout'] * 1000)

		# return all connections
		return connections[hash]


# Close all connections for a given config file
#
# @type  hash: string
# @param hash: connection cache hash (config filepath hash actually)
#
# @global connections
def closeConnection(hash):
	if isString(hash) is False:
		printMessage("Error closing connection: connection hash must be a string, " + str(type(hash)) + " given")
		return

	if hash not in connections:
		return

	try:
		for connection in connections[hash]:
			connection.close(connections, hash)
			printMessage("Closed", connection.name)

		if len(connections[hash]) == 0:
			connections.pop(hash)

	except Exception as e:
		printMessage("Error when closing connection (key: " + hash + ") [Exception: " + stringifyException(e) + "]")
		handleException(e)


# Returns a new worker
def createWorker():
	queue = Worker(workerLimit, makeConnection, loadConfig)

	if debugWorkers and isDebug:
		queue.enableDebug()

	return queue


# ==== Executive functions ======================================================================

class SyncObject(object):

	def __init__(self):
		self.onFinish = []

	def addOnFinish(self, callback):
		self.onFinish.append(callback)

		return self

	def triggerFinish(self, args):
		for finish in self.onFinish:
			if finish is not None:
				finish(args)


# Generic synchronization command
class SyncCommand(SyncObject):

	def __init__(self, file_path, config_file_path):
		SyncObject.__init__(self)

		if sys.version[0] == '3' and type(file_path) is bytes:
			file_path = file_path.decode('utf-8')

		self.running = True
		self.closed = False
		# has exclusive ownership of connection?
		self.ownConnection = False
		self.file_path = file_path
		self.config_file_path = config_file_path

		if isString(config_file_path) is False:
			printMessage("Cancelling " + self.getIdentification() + ": invalid config_file_path given (type: " + str(type(config_file_path)) + ")")
			self.close()
			return

		if os.path.exists(config_file_path) is False:
			printMessage("Cancelling " + self.getIdentification() + ": config_file_path: No such file")
			self.close()
			return

		self.config = loadConfig(config_file_path)
		if file_path is not None:
			self.basename = os.path.relpath(file_path, os.path.dirname(config_file_path))

		self.config_hash = getFilepathHash(self.config_file_path)
		self.connections = None
		self.worker = None

	def getIdentification(self):
		return str(self.__class__.__name__) + " [" + str(self.file_path) + "]"

	def setWorker(self, worker):
		self.worker = worker

	def setConnection(self, connections):
		self.connections = connections
		self.ownConnection = False

	def _createConnection(self):
		if self.connections is None:
			self.connections = getConnection(self.config_hash, self.config, False)
			self.ownConnection = True

	def _localizePath(self, config, remote_path):
		path = remote_path
		if path.find(config['path']) == 0:
			path = os.path.realpath(os.path.join(os.path.dirname(self.config_file_path), remote_path[len(config['path']):]))

		return path

	def execute(self):
		raise NotImplementedError("Abstract method")

	def close(self):
		self.running = False
		self.closed = True

	def _closeConnection(self):
		closeConnection(getFilepathHash(self.config_file_path))

	def whitelistConnections(self, whitelistConnections):
		toBeRemoved = []
		for name in self.config['connections']:
			if name not in whitelistConnections:
				toBeRemoved.append(name)

		for name in toBeRemoved:
			self.config['connections'].pop(name)

		return self

	def isRunning(self):
		return self.running

	def __del__(self):
		self.running = False

		if hasattr(self, 'config_hash') and self.config_hash in usingConnections:
			usingConnections.remove(self.config_hash)

		if hasattr(self, 'ownConnection'):
			if self.ownConnection:
				for connection in self.connections:
					if isDebug:
						printMessage("Closing connection")
					connection.close()
			elif hasattr(self, 'worker') and self.worker is not None:
				self.worker = None


# Transfer-related sychronization command
class SyncCommandTransfer(SyncCommand):

	def __init__(self, file_path, config_file_path, progress=None, onSave=False, disregardIgnore=False, whitelistConnections=[], forcedSave=False):
		SyncCommand.__init__(self, file_path, config_file_path)

		self.progress = progress
		self.onSave = onSave
		self.disregardIgnore = False

		# global ignore
		if disregardIgnore is False and ignore is not None and re_ignore.search(self.file_path) is not None:
			if self._onPreConnectionRemoved():
				printMessage("File globally ignored: {" + os.path.basename(self.file_path) + "}", onlyVerbose=True)
				self.close()
				return

		toBeRemoved = []
		for name in self.config['connections']:

			# on save
			if self.config['connections'][name]['upload_on_save'] is False and onSave is True and forcedSave is False:
				toBeRemoved.append(name)
				continue

			# ignore
			if disregardIgnore is False and self.config['connections'][name]['ignore'] is not None and re.search(self.config['connections'][name]['ignore'], self.file_path):
				if self._onPreConnectionRemoved():
					toBeRemoved.append(name)

				printMessage("File ignored by rule: {" + self.basename + "}", name, True)
				continue

			# whitelist
			if len(whitelistConnections) > 0 and name not in whitelistConnections:
				toBeRemoved.append(name)
				continue

		for name in toBeRemoved:
			self.config['connections'].pop(name)

	# Code that needs to run when a connection is removed (ignored) 
	#
	# @return bool: truly remove?
	def _onPreConnectionRemoved(self):
		if self.progress is not None:
			self.progress.progress()

		return True

	# Get connections of this command that were not removed due to config, ignore etc.
	def getConnectionsApplied(self):
		return self.config['connections']

	# Creates a message when transfer is finished and sends it to console / bar / system
	def finishMessage(self, title, stored, wasFinished):
		notify = title + "ing "
		if self.progress is None or self.progress.getTotal() == 1:
			notify += "{" + self.basename + "} "
		else:
			notify += str(self.progress.getTotal()) + " files "
		notify += "finished!"

		if self.progress is not None and self.progress.isFinished() and wasFinished is False:
			dumpMessage(getProgressMessage(stored, self.progress, notify))
		else:
			dumpMessage(getProgressMessage(stored, self.progress, title + "ed ", self.basename))

		if systemNotifications and self.progress is None or (self.progress.isFinished() and wasFinished is False):
			systemNotify(notify)


# Upload command
class SyncCommandUpload(SyncCommandTransfer):

	def __init__(self, file_path, config_file_path, progress=None, onSave=False, disregardIgnore=False, whitelistConnections=[], forcedSave=False):
		self.delayed = False
		self.skip = False

		SyncCommandTransfer.__init__(self, file_path, config_file_path, progress, onSave, disregardIgnore, whitelistConnections, forcedSave)

		self.watcher = FileWatcher(self.config_file_path, self.config['connections'])
		if os.path.exists(file_path) is False:
			printMessage("Cancelling " + self.getIdentification() + ": file_path: No such file")
			self.close()
			return

	# Code that needs to run when a connection is removed (ignored)
	#
	# @return bool: truly remove?
	def _onPreConnectionRemoved(self):
		SyncCommandTransfer._onPreConnectionRemoved(self)

		# when saving and has afterwatch, don't remove completely, only skip
		# so that we at least upload those changed files
		if self._hasAfterWatch() and self.onSave:
			self.skip = True
			return False

		return True

	# Returns whether any of the config entries has after_save_watch enabled
	# Can't be in FileWatcher due to cycling dependency with config and _onPreConnectionRemoved
	def _hasAfterWatch(self):
		for name in self.config['connections']:
			if self.config['connections'][name]['after_save_watch']:
				return True

		return False

	# ???
	def setScanned(self, event, name, data):
		self.watcher.setScanned(event, name, data)

	# Executes command
	def execute(self):
		if self.closed is True:
			printMessage("Cancelling " + self.getIdentification() + ": command is closed")
			self.close()
			return

		if len(self.config['connections']) == 0:
			printMessage("Cancelling " + self.getIdentification() + ": zero connections apply")
			self.close()
			return

		self._createConnection()

		# afterwatch
		if self.onSave is True:
			try:
				self.watcher.prepare()
			except Exception as e:
				printMessage("Watching failed: {" + self.basename + "} [Exception: " + stringifyException(e) + "]", "", False, True)

		usingConnections.append(self.config_hash)
		stored = []
		index = -1

		for name in self.config['connections']:
			index += 1

			try:
				self._createConnection()

				# identification
				connection = self.connections[index]
				id = os.urandom(32)
				scheduledUploads[self.file_path] = id

				# action
				def action():
					try:

						# cancelled
						if self.file_path not in scheduledUploads or scheduledUploads[self.file_path] != id:
							return

						# process
						if self.skip is False:
							connection.put(self.file_path)

						stored.append(name)

						if self.skip is False:
							printMessage("Uploaded {" + self.basename + "}", name)
						else:
							printMessage("Ignored {" + self.basename + "}", name)

						# cleanup
						scheduledUploads.pop(self.file_path)

						if self.delayed is True:
							for change in self.watcher.getChangedFiles(name):
								if change.isSameFilepath(self.file_path):
									continue

								change = change.getPath()
								command = SyncCommandUpload(change, getConfigFile(change), None, False, True, [name])

								if self.worker is not None:
									command.setWorker(self.worker)
									self.worker.addCommand(command, self.config_file_path)
								else:
									command.execute()

							self.delayed = False
							self.__del__()

						# no need to handle progress, delay action only happens with single uploads
						self.triggerFinish(self.file_path)

					except Exception as e:
						printMessage("Upload failed: {" + self.basename + "} [Exception: " + stringifyException(e) + "]", name, False, True)
						handleException(e)

					finally:
						self.running = False

				# delayed
				if self.onSave is True and self.config['connections'][name]['upload_delay'] > 0:
					self.delayed = True
					printMessage("Delaying processing " + self.basename + " by " + str(self.config['connections'][name]['upload_delay']) + " seconds", name, onlyVerbose=True)
					sublime.set_timeout(action, self.config['connections'][name]['upload_delay'] * 1000)
				else:
					action()

			except IndexError:
				continue

			except EOFError:
				printMessage("Connection has been terminated, please retry your action", name, False, True)
				self._closeConnection()

			except Exception as e:
				printMessage("Upload failed: {" + self.basename + "} [Exception: " + stringifyException(e) + "]", name, False, True)
				handleException(e)

		if self.progress is not None:
			self.progress.progress()

		if len(stored) > 0:
			self.finishMessage("Upload", stored, True)

	def __del__(self):
		if hasattr(self, 'delayed') and self.delayed is False:
			SyncCommand.__del__(self)
		else:
			self.closed = True
			self.running = False


# Download command
class SyncCommandDownload(SyncCommandTransfer):

	def __init__(self, file_path, config_file_path, progress=None, onSave=False, disregardIgnore=False, whitelistConnections=[], forcedSave = False):
		SyncCommandTransfer.__init__(self, file_path, config_file_path, progress, onSave, disregardIgnore, whitelistConnections, forcedSave)

		self.isDir = False
		self.forced = False
		self.skip = False

	def setIsDir(self):
		self.isDir = True

		return self

	def setForced(self):
		self.forced = True

		return self

	def setSkip(self):
		self.skip = True

		return self

	def execute(self):
		self.forced = True

		if self.closed is True:
			printMessage("Cancelling " + self.getIdentification() + ": command is closed")
			self.close()
			return

		if len(self.config['connections']) == 0:
			printMessage("Cancelling " + self.getIdentification() + ": zero connections apply")
			self.close()
			return

		self._createConnection()

		usingConnections.append(self.config_hash)
		index = -1
		stored = []

		for name in self.config['connections']:
			index += 1

			try:
				if self.isDir or os.path.isdir(self.file_path):
					contents = self.connections[index].list(self.file_path)
					if type(contents) is not list:
						printMessage("List returned no entries {0}".format(self.file_path))
						continue

					if os.path.exists(self.file_path) is False:
						os.makedirs(self.file_path)

					if self.progress:
						for entry in contents:
							if entry.isDirectory() is False:
								self.progress.add([entry.getName()])

					self.running = False
					for entry in contents:
						full_name = os.path.join(self.file_path, entry.getName())

						command = SyncCommandDownload(full_name, self.config_file_path, progress=self.progress, disregardIgnore=self.disregardIgnore)

						if self.forced:
							command.setForced()

						if entry.isDirectory() is True:
							command.setIsDir()
						elif not self.forced and entry.isNewerThan(full_name) is True:
							command.setSkip()

						if self.worker is not None:
							command.setWorker(self.worker)
							self.worker.addCommand(command, self.config_file_path)
						else:
							command.execute()

				else:
					if not self.skip or self.forced:
						self.connections[index].get(self.file_path, blockCallback = lambda: dumpMessage(getProgressMessage([name], self.progress, "Downloading", self.basename)))
						printMessage("Downloaded {" + self.basename + "}", name)
						self.triggerFinish(self.file_path)
					else:
						printMessage("Skipping {" + self.basename + "}", name)

					stored.append(name)

			except IndexError:
				continue

			except FileNotFoundException:
				printMessage("Remote file not found", name, False, True)
				handleException(e)

			except EOFError:
				printMessage("Connection has been terminated, please retry your action", name, False, True)
				self._closeConnection()

			except Exception as e:
				printMessage("Download of {" + self.basename + "} failed [Exception: " + stringifyException(e) + "]", name, False, True)
				handleException(e)

			finally:
				self.running = False
				break

		wasFinished = False
		if self.progress is None or self.progress.isFinished() is False:
			wasFinished = True

		if self.progress is not None and self.isDir is not True:
			self.progress.progress()

		if len(stored) > 0:
			self.finishMessage("Download", stored, wasFinished)

			file_path = self.file_path
			def refresh():
				view = sublime.active_window().active_view()
				if view is not None and view.file_name() == file_path:
					view.run_command("revert")

			sublime.set_timeout(refresh, 1)


# Rename command
class SyncCommandRename(SyncCommand):

	def __init__(self, file_path, config_file_path, new_name):
		if os.path.exists(file_path) is False:
			printMessage("Cancelling " + self.getIdentification() + ": file_path: No such file")
			self.close()
			return

		if isString(new_name) is False:
			printMessage("Cancelling SyncCommandRename: invalid new_name given (type: " + str(type(new_name)) + ")")
			self.close()
			return

		if len(new_name) == 0:
			printMessage("Cancelling SyncCommandRename: empty new_name given")
			self.close()
			return

		self.new_name = new_name
		self.dirname = os.path.dirname(file_path)
		SyncCommand.__init__(self, file_path, config_file_path)

	def execute(self):
		if self.closed is True:
			printMessage("Cancelling " + self.getIdentification() + ": command is closed")
			self.close()
			return

		if len(self.config['connections']) == 0:
			printMessage("Cancelling " + self.getIdentification() + ": zero connections apply")
			self.close()
			return

		self._createConnection()

		usingConnections.append(self.config_hash)
		index = -1
		renamed = []

		exists = []
		remote_new_name = os.path.join( os.path.split(self.file_path)[0], self.new_name)
		for name in self.config['connections']:
			index += 1

			check = None
			try:
				check = self.connections[index].list(remote_new_name)
			except FileNotFoundException:
				pass

			if type(check) is list and len(check) > 0:
				exists.append(name)

		def action(forced=False):
			index = -1

			for name in self.config['connections']:
				index += 1

				try:
					self.connections[index].rename(self.file_path, self.new_name, forced)
					printMessage("Renamed {" + self.basename + "} -> {" + self.new_name + "}", name)
					renamed.append(name)

				except IndexError:
					continue

				except TargetAlreadyExists as e:
					printMessage(stringifyException(e))

				except EOFError:
					printMessage("Connection has been terminated, please retry your action", name, False, True)
					self._closeConnection()

				except Exception as e:
					if str(e).find("No such file or directory"):
						printMessage("Remote file not found", name, False, True)
						renamed.append(name)
					else:
						printMessage("Renaming failed: {" + self.basename + "} -> {" + self.new_name + "} [Exception: " + stringifyException(e) + "]", name, False, True)
						handleException(e)

			# message
			if len(renamed) > 0:
				# rename file
				replace(self.file_path, os.path.join(self.dirname, self.new_name))

				self.triggerFinish(self.file_path)

				printMessage("Remotely renamed {" + self.basename + "} -> {" + self.new_name + "}", "remotes: " + ','.join(renamed), status=True)


		if len(exists) == 0:
			action()
		else:
			def sync(index):
				if index is 0:
					printMessage("Renaming: overwriting target")
					action(True)
				else:
					printMessage("Renaming: keeping original")

			overwrite = []
			overwrite.append("Overwrite remote file? Already exists in:")
			for remote in exists:
				overwrite.append(remote + " [" + self.config['connections'][name]['host'] + "]")

			cancel = []
			cancel.append("Cancel renaming")
			for remote in exists:
				cancel.append("")

			sublime.set_timeout(lambda: sublime.active_window().show_quick_panel([ overwrite, cancel ], sync), 1)


# Upload command
class SyncCommandDelete(SyncCommandTransfer):

	def __init__(self, file_path, config_file_path, progress=None, onSave=False, disregardIgnore=False, whitelistConnections=[]):
		SyncCommandTransfer.__init__(self, file_path, config_file_path, progress, False, False, whitelistConnections)

	def execute(self):
		if self.closed is True:
			printMessage("Cancelling " + self.getIdentification() + ": command is closed")
			return

		if self.progress is not None:
			self.progress.progress()

		if len(self.config['connections']) == 0:
			printMessage("Cancelling " + self.getIdentification() + ": zero connections apply")
			return

		self._createConnection()
		usingConnections.append(self.config_hash)
		deleted = []
		index = -1

		for name in self.config['connections']:
			index += 1

			try:
				# identification
				connection = self.connections[index]

				# action
				try:
					# process
					connection.delete(self.file_path)
					deleted.append(name)
					printMessage("Deleted {" + self.basename + "}", name)

				except FileNotFoundException:
					deleted.append(name)
					printMessage("No remote version of {" + self.basename + "} found", name)

				except Exception as e:
					printMessage("Delete failed: {" + self.basename + "} [Exception: " + stringifyException(e) + "]", name, False, True)
					handleException(e)

			except IndexError:
				continue

			except FileNotFoundException:
				printMessage("Remote file not found", name, False, True)
				deleted.append(name)
				continue

			except EOFError:
				printMessage("Connection has been terminated, please retry your action", name, False, True)
				self._closeConnection()

			except Exception as e:
				if str(e).find("No such file or directory"):
					printMessage("Remote file not found", name, False, True)
					deleted.append(name)
				else:
					printMessage("Delete failed: {" + self.basename + "} [Exception: " + stringifyException(e) + "]", name, False, True)
					handleException(e)

		if len(deleted) > 0:
			if os.path.exists(self.file_path):
				if os.path.isdir(self.file_path):
					shutil.rmtree(self.file_path)
				else:
					os.remove(self.file_path)

			self.triggerFinish(self.file_path)

			dumpMessage(getProgressMessage(deleted, self.progress, "Deleted", self.basename))


# Rename command
class SyncCommandGetMetadata(SyncCommand):

	def execute(self):
		if self.closed is True:
			printMessage("Cancelling " + self.getIdentification() + ": command is closed")
			return

		if len(self.config['connections']) == 0:
			printMessage("Cancelling " + self.getIdentification() + ": zero connections apply")
			return

		self._createConnection()

		usingConnections.append(self.config_hash)
		index = -1
		results = []

		for name in self.config['connections']:
			index += 1

			try:
				metadata = self.connections[index].list(self.file_path)

				if type(metadata) is list and len(metadata) > 0:
					results.append({
						'connection': name,
						'metadata': metadata[0]
					})

			except IndexError:
				continue

			except FileNotFoundException:
				raise

			except EOFError:
				printMessage("Connection has been terminated, please retry your action", name, False, True)
				self._closeConnection()

			except Exception as e:
				printMessage("Getting metadata failed: {" + self.basename + "} [Exception: " + stringifyException(e) + "]", name, False, True)
				handleException(e)

		return results


def performRemoteCheck(file_path, window, forced = False, whitelistConnections=[]):
	if isString(file_path) is False:
		return

	if window is None:
		return

	basename = os.path.basename(file_path)

	printMessage("Checking {" + basename + "} if up-to-date", status=True)

	config_file_path = getConfigFile(file_path)
	if config_file_path is None:
		return printMessage("Found no config > for file: " + file_path, status=True)

	config = loadConfig(config_file_path)
	try:
		metadata = SyncCommandGetMetadata(file_path, config_file_path)
		if len(whitelistConnections) > 0:
			metadata.whitelistConnections(whitelistConnections)
		metadata = metadata.execute()
	except FileNotFoundException:
		printMessage("Remote file not found", status=True)
		return
	except Exception as e:
		printMessage("Error when getting metadata: " + stringifyException(e))
		handleException(e)
		metadata = []

	if type(metadata) is not list:
		return printMessage("Invalid metadata response, expected list, got " + str(type(metadata)))

	if len(metadata) == 0:
		return printMessage("No version of {" + basename + "} found on any server", status=True)

	newest = []
	oldest = []
	every = []

	for entry in metadata:
		if forced is False and entry['metadata'].isDifferentSizeThan(file_path) is False:
			continue

		if entry['metadata'].isNewerThan(file_path):
			newest.append(entry)
			every.append(entry)
		else:
			oldest.append(entry)

			if entry['metadata'].isDifferentSizeThan(file_path):
				every.append(entry)

	if len(every) > 0:
		every = metadata
		sorted(every, key=lambda entry: entry['metadata'].getLastModified())
		every.reverse()

		connectionCount = len(every)

		def sync(index):
			if index == connectionCount + 1:
				return RemoteSyncCall(file_path, getConfigFile(file_path), True).start()

			if index > 0:
				if isDebug:
					i = 0
					for entry in every:
						printMessage("Listing connection " + str(i) + ": " + str(entry['connection']))
						i += 1

					printMessage("Index selected: " + str(index - 1))

				return RemoteSyncDownCall(file_path, getConfigFile(file_path), True, whitelistConnections=[every[index - 1]['connection']]).start()

		filesize = os.path.getsize(file_path)
		allItems = []
		items = []
		items.append("Keep current " + os.path.basename(file_path))
		items.append("Size: " + str(round(float(os.path.getsize(file_path)) / 1024, 3)) + " kB")
		items.append("Last modified: " + formatTimestamp(os.path.getmtime(file_path)))
		allItems.append(items)
		index = 1

		for item in every:
			item_filesize = item['metadata'].getFilesize()

			if item_filesize == filesize:
				item_filesize = "same size"
			else:
				if item_filesize > filesize:
					item_filesize = str(round(item_filesize / 1024, 3)) + " kB ~ larger"
				else:
					item_filesize = str(round(item_filesize / 1024, 3)) + " kB ~ smaller"

			time = str(item['metadata'].getLastModifiedFormatted(timeFormat))

			if item in newest:
				time += " ~ newer"
			else:
				time += " ~ older"


			items = []
			items.append("Get from " + item['connection'] + " [" + config['connections'][ item['connection'] ]['host'] + "]")
			items.append("Size: " + item_filesize)
			items.append("Last modified: " + time)
			allItems.append(items)
			index += 1

		upload = []
		upload.append("Upload file " + os.path.basename(file_path))
		upload.append("Size: " + str(round(float(os.path.getsize(file_path)) / 1024, 3)) + " kB")
		upload.append("Last modified: " + formatTimestamp(os.path.getmtime(file_path)))
		allItems.append(upload)

		sublime.set_timeout(lambda: window.show_quick_panel(allItems, sync), 1)
	else:
		printMessage("All remote versions of {" + basename + "} are of same size and older", status=True)


class ShowInfo(SyncCommand):

	def execute(self, window):
		if self.closed:
			printMessage("Cancelling " + self.getIdentification() + ": command closed")
			return

		if len(self.config['connections']) == 0:
			printMessage("Cancelling " + self.getIdentification() + ": zero connections apply")
			return

		self._createConnection()

		usingConnections.append(self.config_hash)
		index = -1
		results = []

		for name in self.config['connections']:
			index += 1

			try:
				info = self.connections[index].getInfo()

				if type(info) is dict:
					results.append(info)

			except IndexError:
				continue

			except Exception as e:
				printMessage("Getting info failed [Exception: " + stringifyException(e) + "]", name, False, True)
				handleException(e)

		maxFeats = 0
		for item in results:
			if len(item['features']) > maxFeats:
				maxFeats = len(item['features'])

		output = []
		for item in results:
			if item['config']['tls']:
				encryption = "enabled"
			else:
				encryption = "disabled"

			if item['canEncrypt'] is None:
				encryption += " [unconfirmed]"
			elif item['canEncrypt'] is False:
				encryption += " [NOT SUPPORTED]"
			else:
				encryption += " [SUPPORTED]"

			entry = []
			entry.append(item['name'] + " [" + item['config']['host'] + "]")
			entry.append("Type: " + item['type'])
			entry.append("User: " + item['config']['username'])
			entry.append("Encryption: " + encryption)

			if "MFMT" in item['features']:
				entry.append("Last modified: SUPPORTED")
			else:
				entry.append("Last modified: NOT SUPPORTED")

			entry.append("")
			entry.append("Server features:")

			feats = 0
			for feat in item['features']:
				entry.append(feat)
				feats = feats + 1

			if feats < maxFeats:
				for i in range(1, maxFeats - feats):
					entry.append("")

			output.append(entry)

		sublime.set_timeout(lambda: window.show_quick_panel(output, None), 1)


class SyncNavigator(SyncCommand):

	def __init__(self, file_path, config_file_path, connection_name = None, path = None, remotePath = None):
		self.configConnection = None
		self.configName = None
		self.files = []
		self.defaultPath = path
		self.defaultRemotePath = remotePath

		SyncCommand.__init__(self, None, config_file_path)

		if connection_name is not None:
			self.selectConnection(connection_name)

	def execute(self):
		if self.closed is True:
			printMessage("Cancelling " + self.getIdentification() + ": command is closed")
			return

		if len(self.config['connections']) == 0:
			printMessage("Cancelling " + self.getIdentification() + ": zero connections apply")
			return

		usingConnections.append(self.config_hash)
		index = -1
		results = []

		if len(self.config['connections']) > 1 and self.configConnection is None:
			self.listConnections()
		else:
			if self.configConnection is None:
				for name in self.config['connections']:
					self.selectConnection(name)

			if self.defaultPath:
				self.listFiles(self.defaultPath)
			elif self.defaultRemotePath:
				self.listFiles(self.defaultRemotePath, True)

	def listConnections(self):
		connections = []
		names = []

		for name in self.config['connections']:
			connection = self.config['connections'][name]
			connections.append([ name, "Host: " + connection['host'], "Path: " + connection['path'] ])
			names.append(name)

		def handleConnectionSelection(index):
			if index == -1:
				return

			self.selectConnection(names[index])
			self.listFiles(self.defaultPath)

		sublime.set_timeout(lambda: sublime.active_window().show_quick_panel(connections, handleConnectionSelection), 1)

	def selectConnection(self, name):
		self.configConnection = self.config['connections'][name]
		self.configName = name
		self.config['connections'] = {}
		self.config['connections'][name] = self.configConnection

	def updateNavigateLast(self, path):
		navigateLast['config_file'] = self.config_file_path
		navigateLast['connection_name'] = self.configName
		navigateLast['path'] = path

	def listFiles(self,path=None,forced=False):
		if self.closed is True:
			printMessage("Cancelling " + self.getIdentification() + ": command is closed")
			return

		self._createConnection()
		connection = self.connections[0]

		# figure out path
		remote = True
		if path is None or path == self.defaultPath or self.defaultPath is None:
			remote = False
		if path is None:
			path = os.path.dirname(self.config_file_path)
		if forced:
			remote = True

		self.updateNavigateLast(path)

		# get contents
		contents = connection.list(path, remote, True)
		contents = addLinks(contents, connection.getMappedPath(path, remote))
		contents = sorted(contents, key = lambda entry: (entry.getName() != "..", entry.isDirectory() is False, entry.getName().lower()))
		content = []

		# add header
		currentFolder = os.path.basename(connection.getNormpath(path))
		if currentFolder == '..':
			currentFolder = '/'

		if displayDetails:
			header = self.getDetailedCurrentFolder(currentFolder)
		else:
			header = self.getSimpleCurrentFolder(currentFolder)

		content.extend(header)

		# find current folder
		currentMeta = None
		for meta in contents:
			if meta.getName() == '.':
				for i in range(len(header)):
					self.files.append(meta)
				break

		# add contents
		for meta in contents:
			if displayDetails:
				entry = self.getDetailedEntry(meta, path, connection)
			else:
				entry = self.getSimpleEntry(meta, path, connection)

			if entry:
				content.append(entry)
				self.files.append(meta)

		if len(contents) == 0:
			printMessage("No files found in remote path for local {" + str(path) + "}", status=True)

		def handleMetaSelection(index):
			if index == -1:
				return

			meta = self.files[index]
			self.files = []

			if meta.isDirectory():
				if index >= len(header):
					self.listFiles(meta.getFilepath())
				else:
					self.listFolderActions(meta)
			else:
				self.listFileActions(meta)

		sublime.set_timeout(lambda: sublime.active_window().show_quick_panel(content, handleMetaSelection), 1)

	def getSimpleCurrentFolder(self, currentFolder):
		return [[ currentFolder + "/" ]]

	def getDetailedCurrentFolder(self, currentFolder):
		entry = [currentFolder, "• Current folder", "• Click to list actions"]
		if displayPermissions:
			entry.append("")
		return [entry]

	def getSimpleEntry(self, meta, path, connection):
		entry = []
		if meta.isDirectory():
			if meta.getName() == '.' or (meta.getName() == '..' and connection.getNormpath(path) == '/'):
				return None

			if meta.getName() == '..':
				entry.append("\t" + decode("▴ .."))
			else:
				entry.append("\t" + decode("▾ ") + decode(meta.getName()))
		else:
			entry.append("\t\t" + decode(meta.getName()))

		return entry

	def getDetailedEntry(self, meta, path, connection):
		entry = []
		if meta.isDirectory():
			if meta.getName() == '.' or (meta.getName() == '..' and connection.getNormpath(path) == '/'):
				return None

			entry.append("[" + decode(meta.getName()) + "]")
			entry.append("Directory")
		else:
			entry.append(decode(meta.getName()))
			entry.append("Size: " + meta.getHumanFilesize())


		if displayDetails:
			entry.append("Last modified: " + meta.getLastModifiedFormatted(displayTimestampFormat))

			if displayPermissions:
				entry.append("Permissions: " + meta.getPermissions())

			entry.append("Path: " + meta.getPath())

		return entry

	def listFolderActions(self, meta, action = None):	
		if self.closed is True:
			printMessage("Cancelling " + self.getIdentification() + ": command is closed")
			return

		self._createConnection()
		connection = self.connections[0]
		path = meta.getPath()
		localFile = connection.getLocalPath( str(meta.getPath() + '/' + meta.getName()).replace('/.',''), os.path.dirname(self.config_file_path))
		exists = 0

		name = meta.getName()
		if name == '.':
			split = re_thisFolder.search(meta.getPath())
			if split is not None:
				name = split.group(1)
		if name == '..':
			split = re_parentFolder.search(meta.getPath())
			if split is not None:
				name = split.group(1)
			else:
				name = '/'

			self.listFiles(meta.getPath() + '/' + meta.getName())
			return

		actions = []
		actions.append("Open " + decode(name) + " folder")
		actions.append("Back")
		actions.append("Download folder")

		if os.path.exists(localFile):
			actions.append("Upload folder")
			exists = 1

		actions.append("Remove folder")
		actions.append("Rename folder")
		actions.append("Change permissions")
		actions.append("Show details")
		actions.append("Copy path")

		def handleAction(index):
			if index == -1:
				return

			if index == 0:
				self.listFiles(meta.getPath() + '/' + meta.getName())
				return

			if index == 1:
				self.listFiles(meta.getPath())
				return

			if index == 2:
				call = RemoteSyncDownCall([[localFile, getConfigFile(localFile)]], None, False, True)
				call.setIsDir()
				call.start()
				return

			if exists and index == 3:
				RemoteSyncCall(gatherFiles([localFile]), None, False, True).start()
				return

			if index == 3 + exists:
				RemoteSyncDelete(localFile).start()
				return

			if index == 4 + exists:
				try:
					sublime.active_window().run_command("ftp_sync_rename", { "paths": [ localFile ] })
				except Exception as e:
					handleException(e)
				return

			if index == 5 + exists:
				def permissions(newPermissions):
					self._createConnection()
					connection = self.connections[0]
					connection.cwd(meta.getPath())
					connection.chmod(meta.getName(), newPermissions)

					printMessage("Properties of " + meta.getName() + " changed to " + newPermissions, status=True)

				sublime.active_window().show_input_panel('Change permissions to:', self.configConnection['default_folder_permissions'], permissions, None, None)

			if index == 6 + exists:
				info = []
				info.append(meta.getName())
				info.append("[Directory]")
				info.append("Path: " + str(meta.getPath())[len(self.configConnection['path']):] + '/' + meta.getName().replace('/./', '/'))
				info.append("Permissions: " + meta.getPermissions() + " (" + meta.getPermissionsNumeric() + ")")
				if connection.hasTrueLastModified():
					info.append("Last Modified: " + meta.getLastModifiedFormatted())
				else:
					info.append("Last upload time: " + meta.getLastModifiedFormatted())

				info.append("")
				if os.path.exists(localFile):
					info.append("[Has local version]")
					info.append("Local last modified: " + formatTimestamp(os.path.getmtime(localFile), displayTimestampFormat))
					if sublime.platform() == 'windows':
						info.append("Local created: " + formatTimestamp(os.path.getctime(localFile), displayTimestampFormat))
				else:
					info.append("[No local version]")

				sublime.set_timeout(lambda: sublime.active_window().show_quick_panel([info], None), 1)
				return

			if index == 7 + exists:
				get_path = meta.getPath()
				sublime.set_clipboard(get_path)
				return


		if action is None:
			sublime.set_timeout(lambda: sublime.active_window().show_quick_panel(actions, handleAction), 1)
		else:
			handleAction(action)

	def listFileActions(self, meta, action = None):
		if self.closed is True:
			printMessage("Cancelling " + self.getIdentification() + ": command is closed")
			return

		path = meta.getPath() + '/' + meta.getName()
		self._createConnection()
		connection = self.connections[0]
		localFile = connection.getLocalPath(meta.getPath() + '/' + meta.getName(), os.path.dirname(self.config_file_path))

		exists = 0
		hasSidebar = packageExists("SideBarEnhancements")

		actions = []
		actions.append("Back")
		actions.append("Download file")

		if os.path.exists(localFile):
			actions.append("Upload file")
			exists = 1

		actions.append("Remove file")
		actions.append("Rename file")

		if hasSidebar:
			actions.append("Open / run")

		actions.append("Change permissions")
		actions.append("Show details")

		def handleAction(index):
			if index == -1:
				return

			if index == 0:
				self.listFiles(meta.getPath())
				return

			if index == 1:
				def dopen(args):
					try:
						sublime.set_timeout(lambda: sublime.active_window().open_file(args), 1)
					except Exception as e:
						handleException(e)

				call = RemoteSyncDownCall(localFile, getConfigFile(self.config_file_path), False, True)
				if settings.get('browse_open_on_download'):
					call.onFinish(dopen)
				call.start()
				return

			if exists and index == 2:
				RemoteSyncCall(gatherFiles([localFile]), None, True, True).start()
				return

			if index == 2 + exists:
				RemoteSyncDelete(localFile).start()
				return

			if index == 3 + exists:
				try:
					sublime.active_window().run_command("ftp_sync_rename", { "paths": [ localFile ] })
				except Exception as e:
					handleException(e)
				return

			if hasSidebar and index == 4 + exists:
				def openRun(args):
					sublime.set_timeout(lambda: sublime.active_window().run_command("side_bar_open", {"paths": [ args ]}), 1)

				# download
				call = RemoteSyncCall(gatherFiles([localFile]), None, False, True)
				call.onFinish(openRun)
				call.start()
				return

			if index == 4 + exists + int(hasSidebar):
				def permissions(newPermissions):
					self._createConnection()
					connection = self.connections[0]
					connection.cwd(meta.getPath())
					connection.chmod(meta.getName(), newPermissions)

					printMessage("Properties of " + meta.getName() + " changed to " + newPermissions, status=True)

				sublime.active_window().show_input_panel('Change permissions to:', self.configConnection['default_folder_permissions'], permissions, None, None)
				return

			if index == 5 + exists + int(hasSidebar):
				info = []
				info.append(meta.getName())
				info.append("[File]")
				info.append("Path: " + str(meta.getPath())[len(self.configConnection['path']):] + '/' + meta.getName().replace('/./', '/'))
				info.append("Size: " + str(round(meta.getFilesize()/1024,3)) + " kB")
				info.append("Permissions: " + meta.getPermissions() + " (" + meta.getPermissionsNumeric() + ")")
				if connection.hasTrueLastModified():
					info.append("Last Modified: " + meta.getLastModifiedFormatted())
				else:
					info.append("Last upload time: " + meta.getLastModifiedFormatted())

				info.append("")
				if os.path.exists(localFile):
					info.append("[Has local version]")
					info.append("Local size: " + str(round(float(os.path.getsize(localFile)) / 1024, 3)) + " kB")
					info.append("Local last modified: " + formatTimestamp(os.path.getmtime(localFile), displayTimestampFormat))
					if sublime.platform() == 'windows':
						info.append("Local created: " + formatTimestamp(os.path.getctime(localFile), displayTimestampFormat))
				else:
					info.append("[No local version]")

				sublime.set_timeout(lambda: sublime.active_window().show_quick_panel([info], None), 1)
				return

			if index == 6 + exists + int(hasSidebar):
				get_path = meta.getPath()
				sublime.set_clipboard(get_path)
				return

		if action is None:
			sublime.set_timeout(lambda: sublime.active_window().show_quick_panel(actions, handleAction), 1)
		else:
			handleAction(actions)



# ==== Watching ===========================================================================

# list of file paths to be checked on load
checksScheduled = []
# pre_save x post_save upload prevention
preventUpload = []


# File watching
class RemoteSync(sublime_plugin.EventListener):

	def on_pre_save(self, view):
		file_path = getFileName(view)
		config_file_path = getConfigFile(file_path)
		if config_file_path is None:
			return

		def pre_save(_files):
			window = view.window()
			if window is None:
				window = sublime.active_window()

			RemotePresave(file_path, fileToMetafile(file_path), config_file_path, _files, view, window, self.manual_on_post_save).start()

		fillPasswords([[ None, config_file_path ]], pre_save, sublime.active_window())

	def on_post_save(self, view):
		fileName = os.path.basename(view.file_name())
		if fileName == 'FTPSync.sublime-settings':
			sublime.set_timeout(plugin_loaded, 1000)

	def manual_on_post_save(self, file_path):
		config_file_path = getConfigFile(file_path)

		command = RemoteSyncCall(file_path, config_file_path, True)

		if config_file_path in preScan and preScan[config_file_path] is not None:
			command.setPreScan(preScan[config_file_path])

		command.start()

	def on_close(self, view):
		file_path = getFileName(view)

		if file_path is None:
			return

		config_file_path = getConfigFile(file_path)

		if file_path in checksScheduled:
			checksScheduled.remove(file_path)

		if config_file_path is not None:
			closeConnection(getFilepathHash(config_file_path))

	# When a file is loaded and at least 1 connection has download_on_open enabled
	# it will check those enabled if the remote version is newer and offers the newest to download
	def on_load(self, view):
		file_path = getFileName(view)

		if file_path and os.path.basename(file_path) == configName:
			view.set_syntax_file(getConfigSyntax())

		if ignore is not None and re_ignore is not None and re_ignore.search(file_path) is not None:
			return

		if view not in checksScheduled:
			checksScheduled.append(file_path)

			def check():
				if file_path in checksScheduled:

					def execute(files):
						whitelistConnections = []

						config_file_path = getConfigFile(file_path)
						if config_file_path is None:
							return printMessage("Config not found for: " + file_path)

						config = loadConfig(config_file_path)
						for name in config['connections']:
							if config['connections'][name]['download_on_open'] is True:
								whitelistConnections.append(name)

						RemoteSyncCheck(file_path, view.window(), forced=False, whitelistConnections=whitelistConnections).start()

					fillPasswords([[ file_path, getConfigFile(file_path) ]], execute, sublime.active_window())

			sublime.set_timeout(check, downloadOnOpenDelay)


# ==== Threading ===========================================================================

def fillProgress(progress, entry):
	if len(entry) == 0:
		return

	if isString(entry[0]):
		entry = entry[0]

	if type(entry) is list:
		for item in entry:
			fillProgress(progress, item)
	else:
		progress.add([entry])


class RemoteThread(threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self)
		self.preScan = None
		self._whitelistConnetions = []
		self._onFinish = None

	def setPreScan(self, preScan):
		self.preScan = preScan

	def addPreScan(self, command):
		if self.preScan is not None:
			for name in self.preScan:
				command.setScanned('before', name, self.preScan[name])

	def setWhitelistConnections(self, whitelistConnections):
		self._whitelistConnetions = whitelistConnections

	def addWhitelistConnections(self, command):
		if hasattr(self, '_whitelistConnections'):
			command.whitelistConnections(self._whitelistConnetions)

		return command

	def onFinish(self, callback):
		self._onFinish = callback

	def getOnFinish(self):
		if hasattr(self, '_onFinish'):
			return self._onFinish
		else:
			return None


class RemotePresave(RemoteThread):
	def __init__(self, file_path, metafile, config_file_path, _files, view, window, callback):
		self.file_path = file_path
		self.metafile = metafile
		self.config_file_path = config_file_path
		self._files = _files
		self.view = view
		self.window = window
		self.callback = callback
		RemoteThread.__init__(self)

	def run(self):
		_files = self._files
		file_path = self.file_path
		config_file_path = self.config_file_path
		view = self.view
		preScan[config_file_path] = {}
		root = os.path.dirname(config_file_path)
		config = loadConfig(config_file_path)
		blacklistConnections = []

		for connection in config['connections']:
			properties = config['connections'][connection]

			if properties['upload_on_save'] is False:
				blacklistConnections.append(connection)

			watch = properties['after_save_watch']
			if type(watch) is list and len(watch) > 0 and properties['upload_delay'] > 0:
				preScan[config_file_path][connection] = {}

				for folder, filepattern in watch:
					files = gatherMetafiles(filepattern, os.path.join(root, folder))
					preScan[config_file_path][connection].update(files.items())

				if properties['debug_extras']['after_save_watch']:
					printMessage("<debug> dumping pre-scan")
					print ("COUNT: " + str(len(preScan[config_file_path][connection])))
					for change in preScan[config_file_path][connection]:
						print ("Path: " + preScan[config_file_path][connection][change].getPath() + " | Name: " + preScan[config_file_path][connection][change].getName())

		if len(blacklistConnections) == len(config['connections']):
			return

		try:
			metadata = SyncCommandGetMetadata(file_path, config_file_path).execute()
		except FileNotFoundException:
			return
		except Exception as e:
			if str(e).find('No such file'):
				printMessage("No version of {" + os.path.basename(file_path) + "} found on any server", status=True)
			else:
				printMessage("Error when getting metadata: " + stringifyException(e))
				handleException(e)
			metadata = []

		newest = None
		newer = []
		index = 0

		for entry in metadata:
			properties = config['connections'][entry['connection']]

			if 'debug_overwrite_prevention' in properties['debug_extras'] and properties['debug_extras']['debug_overwrite_prevention']:
				printMessage("<debug> dumping overwrite prevention")
				print ("File [local]: " + str(file_path))
				print ("File [remote]: " + str(entry['metadata'].getPath()))
				print ("Enabled: " + str(properties['check_time'] is True))
				print ("Not in blacklist: " + str(entry['connection'] not in blacklistConnections))
				print ("Is remote newer: " + str(entry['metadata'].isNewerThan(self.metafile)))
				print ("Is size different: " + str(entry['metadata'].isDifferentSizeThan(file_path)))
				print ("In overwrite cancelled: " + str(file_path in overwriteCancelled))
				print ("+ [remote] last modified: " + str(entry['metadata'].getLastModified()))
				print ("+ [local] last modified: " + str(self.metafile.getLastModified()))
				print ("+ [remote] size: " + str(entry['metadata'].getFilesize()))
				print ("+ [local] size: " + str(os.path.getsize(file_path)))

			if (entry['connection'] not in blacklistConnections and properties['check_time'] is True and entry['metadata'].isNewerThan(self.metafile) and entry['metadata'].isDifferentSizeThan(file_path)) or file_path in overwriteCancelled:
				newer.append(entry['connection'])

				if newest is None or newest > entry['metadata'].getLastModified():
					newest = index

			index += 1

		if len(newer) > 0:
			preventUpload.append(file_path)

			def sync(index):
				if index is 0:
					printMessage("Overwrite prevention: overwriting")

					if file_path in overwriteCancelled:
						overwriteCancelled.remove(file_path)

					self.callback(self.file_path)
				else:
					printMessage("Overwrite prevention: cancelled upload")

					if file_path not in overwriteCancelled:
						overwriteCancelled.append(file_path)

			yes = []
			yes.append("Yes, overwrite newer")
			yes.append("Last modified: " + metadata[newest]['metadata'].getLastModifiedFormatted())

			for entry in newer:
				yes.append(entry + " [" + config['connections'][entry]['host'] + "]")

			no = []
			no.append("No")
			no.append("Cancel uploading")

			for entry in newer:
				no.append("")

			sublime.set_timeout(lambda: self.window.show_quick_panel([ yes, no ], sync), 1)
		else:
			self.callback(self.file_path)


class RemoteSyncCall(RemoteThread):
	def __init__(self, file_path, config, onSave, disregardIgnore=False, whitelistConnections=[], forcedSave=False):
		self.file_path = file_path
		self.config = config
		self.onSave = onSave
		self.forcedSave = forcedSave
		self.disregardIgnore = disregardIgnore
		self.whitelistConnections = whitelistConnections
		RemoteThread.__init__(self)

	def run(self):
		target = self.file_path

		if isString(target) and self.config is None:
			return False

		elif isString(target):
			command = SyncCommandUpload(target, self.config, onSave=self.onSave, disregardIgnore=self.disregardIgnore, whitelistConnections=self.whitelistConnections, forcedSave=self.forcedSave)
			command.addOnFinish(self.getOnFinish())
			self.addWhitelistConnections(command)
			self.addPreScan(command)
			command.execute()

		elif type(target) is list and len(target) > 0:
			progress = Progress()
			fillProgress(progress, target)

			queue = createWorker()

			for file_path, config in target:
				command = SyncCommandUpload(file_path, config, progress=progress, onSave=self.onSave, disregardIgnore=self.disregardIgnore, whitelistConnections=self.whitelistConnections, forcedSave=self.forcedSave)
				command.addOnFinish(self.getOnFinish())
				self.addWhitelistConnections(command)
				self.addPreScan(command)

				if workerLimit > 1:
					queue.addCommand(command, config)
				else:
					command.execute()


class RemoteSyncDownCall(RemoteThread):
	def __init__(self, file_path, config, disregardIgnore=False, forced=False, whitelistConnections=[]):
		self.file_path = file_path
		self.config = config
		self.disregardIgnore = disregardIgnore
		self.forced = forced
		self.whitelistConnections = []
		self.isDir = False
		RemoteThread.__init__(self)

	def setIsDir(self):
		self.isDir = True

	def run(self):
		target = self.file_path

		if isString(target) and self.config is None:
			return False

		elif isString(target):
			queue = createWorker()

			command = SyncCommandDownload(target, self.config, disregardIgnore=self.disregardIgnore, whitelistConnections=self.whitelistConnections)
			command.addOnFinish(self.getOnFinish())
			self.addWhitelistConnections(command)

			if self.isDir:
				command.setIsDir()

			if self.forced:
				command.setForced()

			if workerLimit > 1:
				command.setWorker(queue)
				queue.addCommand(command, self.config)
			else:
				command.execute()
		elif type(target) is list and len(target) > 0:
			total = len(target)
			progress = Progress(total)
			queue = createWorker()

			for file_path, config in target:
				if os.path.isfile(file_path):
					progress.add([file_path])

				command = SyncCommandDownload(file_path, config, disregardIgnore=self.disregardIgnore, progress=progress, whitelistConnections=self.whitelistConnections)
				command.addOnFinish(self.getOnFinish())
				self.addWhitelistConnections(command)

				if self.isDir:
					command.setIsDir()

				if self.forced:
					command.setForced()

				if workerLimit > 1:
					command.setWorker(queue)
					queue.addCommand(command, config)
				else:
					command.execute()


class RemoteSyncRename(RemoteThread):
	def __init__(self, file_path, config, new_name):
		self.file_path = file_path
		self.new_name = new_name
		self.config = config
		RemoteThread.__init__(self)

	def run(self):
		self.addWhitelistConnections(SyncCommandRename(self.file_path, self.config, self.new_name).addOnFinish(self.getOnFinish())).execute()


class RemoteSyncCheck(RemoteThread):
	def __init__(self, file_path, window, forced=False, whitelistConnections=[]):
		self.file_path = file_path
		self.window = window
		self.forced = forced
		self.whitelistConnections = whitelistConnections
		RemoteThread.__init__(self)

	def run(self):
		performRemoteCheck(self.file_path, self.window, self.forced, self.whitelistConnections)


class RemoteSyncDelete(RemoteThread):
	def __init__(self, file_paths):
		self.file_path = file_paths
		RemoteThread.__init__(self)

	def run(self):
		target = self.file_path

		if isString(target):
			self.file_path = [ target ]

		def sync(index):
			if index is 0:
				self.delete()
			else:
				printMessage("Deleting: cancelled")

		yes = []
		yes.append("Yes, delete the selected items [also remotely]")
		for entry in self.file_path:
			yes.append( getRootPath(entry, '/') )

		no = []
		no.append("No")
		no.append("Cancel deletion")

		for entry in self.file_path:
			if entry == self.file_path[0]:
				continue

			no.append("")

		sublime.set_timeout(lambda: sublime.active_window().show_quick_panel([yes, no], sync), 1)

	def delete(self):
		target = self.file_path
		progress = Progress()
		fillProgress(progress, target)

		for file_path in target:
			command = SyncCommandDelete(file_path, getConfigFile(file_path), progress=progress, onSave=False, disregardIgnore=False, whitelistConnections=[])
			self.addWhitelistConnections(command)
			command.addOnFinish(self.getOnFinish())
			command.execute()


class RemoteNavigator(RemoteThread):
	def __init__(self, config, last = False):
		self.config = config
		self.last = last
		self.command = None
		RemoteThread.__init__(self)

	def setCommand(self, command):
		self.command = command

	def run(self):
		if self.command is None:
			if self.last is True:
				command = SyncNavigator(None, navigateLast['config_file'], navigateLast['connection_name'], None, navigateLast['path'])
			else:
				command = SyncNavigator(None, self.config)
		else:
			command = self.command

		self.addWhitelistConnections(command)
		command.execute()


# ==== Commands ===========================================================================

# Sets up a config file in a directory
class FtpSyncNewSettings(sublime_plugin.WindowCommand):
	def run(self, edit = None, dirs = []):
		if len(dirs) == 0:
			if sublime.active_window() is not None and sublime.active_window().active_view() is not None:
				dirs = [os.path.dirname(sublime.active_window().active_view().file_name())]
			elif sublime.active_window() is not None:
				sublime.active_window().show_input_panel('Enter setup path', '', self.create, None, None)
				return
			else:
				printMessage("Cannot setup file - no folder path selected and no active view (opened file) detected")
				return

		self.create(dirs)

	def create(self, dirs):
		if type(dirs) is Types.text:
			dirs = [dirs]

		for file_path in dirs:
			if os.path.exists(file_path) is False:
				printMessage("Setup: file path does not exist: " + file_path)
				return

		if sublime.version()[0] >= '3':
			content = sublime.load_resource('Packages/FTPSync/ftpsync.default-settings').replace('\r\n', '\n')

			for directory in dirs:
				config = os.path.join(directory, configName)

				if os.path.exists(config) is False:
					with open(config, 'w') as configFile:
						printMessage("Settings file created in: " + config)
						configFile.write(content)

				self.window.open_file(config)
		else:
			default = os.path.join(sublime.packages_path(), 'FTPSync', connectionDefaultsFilename)
			if os.path.exists(default) is False:
				printMessage("Could not find default settings file in {" + default + "}")

				default = os.path.join(__dir__, connectionDefaultsFilename)
				printMessage("Trying filepath {" + default + "}")

			for directory in dirs:
				config = os.path.join(directory, configName)

				invalidateConfigCache(directory)

				if os.path.exists(config) is False:
					printMessage("Settings file created in: " + config)
					shutil.copyfile(default, config)

				self.window.open_file(config)


# Synchronize up selected file/directory
class FtpSyncTarget(sublime_plugin.WindowCommand):
	def run(self, edit, paths):
		def execute(files):
			RemoteSyncCall(files, None, False).start()

		files = gatherFiles(paths)
		fillPasswords(files, execute, sublime.active_window())

# Synchronize up selected file/directory with delay and watch
class FtpSyncTargetDelayed(sublime_plugin.WindowCommand):
	def run(self, edit, paths):
		def execute(files):
			RemoteSyncCall(files, None, True, forcedSave = True).start()

		files = gatherFiles(paths)
		fillPasswords(files, execute, sublime.active_window())


# Synchronize up current file
class FtpSyncCurrent(sublime_plugin.TextCommand):
	def run(self, edit):
		file_path = sublime.active_window().active_view().file_name()

		def execute(files):
			RemoteSyncCall(files[0][0], files[0][1], False).start()

		fillPasswords([[ file_path, getConfigFile(file_path) ]], execute, sublime.active_window())


# Synchronize down current file
class FtpSyncDownCurrent(sublime_plugin.TextCommand):
	def run(self, edit):
		file_path = sublime.active_window().active_view().file_name()

		def execute(files):
			RemoteSyncDownCall(files[0][0], files[0][1], True, False).start()

		fillPasswords([[ file_path, getConfigFile(file_path) ]], execute, sublime.active_window())


# Checks whether there's a different version of the file on server
class FtpSyncCheckCurrent(sublime_plugin.TextCommand):
	def run(self, edit):
		file_path = sublime.active_window().active_view().file_name()
		view = sublime.active_window()

		def execute(files):
			RemoteSyncCheck(file_path, view, True).start()

		fillPasswords([[ file_path, getConfigFile(file_path) ]], execute, sublime.active_window())

# Checks whether there's a different version of the file on server
class FtpSyncRenameCurrent(sublime_plugin.TextCommand):
	def run(self, edit):
		view = sublime.active_window()

		self.original_path = sublime.active_window().active_view().file_name()
		self.folder = os.path.dirname(self.original_path)
		self.original_name = os.path.basename(self.original_path)

		if self.original_path in checksScheduled:
			checksScheduled.remove(self.original_path)

		view.show_input_panel('Enter new name', self.original_name, self.rename, None, None)

	def rename(self, new_name):
		def action():
			def execute(files):
				RemoteSyncRename(self.original_path, getConfigFile(self.original_path), new_name).start()

			fillPasswords([[ self.original_path, getConfigFile(self.original_path) ]], execute, sublime.active_window())

		new_path = os.path.join(os.path.dirname(self.original_path), new_name)
		if os.path.exists(new_path):
			def sync(index):
				if index is 0:
					printMessage("Renaming: overwriting local target")
					action()
				else:
					printMessage("Renaming: keeping original")

			overwrite = []
			overwrite.append("Overwrite local file? Already exists in:")
			overwrite.append("Path: " + new_path)

			cancel = []
			cancel.append("Cancel renaming")

			sublime.set_timeout(lambda: sublime.active_window().show_quick_panel([ overwrite, cancel ], sync), 1)
		else:
			action()


# Synchronize down selected file/directory
class FtpSyncDownTarget(sublime_plugin.WindowCommand):
	def run(self, edit, paths, forced=False):
		filelist = []
		for path in paths:
			filelist.append( [ path, getConfigFile(path) ] )

		def execute(files):
			RemoteSyncDownCall(filelist, None, forced=forced).start()

		fillPasswords(filelist, execute, sublime.active_window())


# Renames a file on disk and in folder
class FtpSyncRename(sublime_plugin.WindowCommand):
	def run(self, edit, paths):
		self.original_path = paths[0]
		self.folder = os.path.dirname(self.original_path)
		self.original_name = os.path.basename(self.original_path)

		if self.original_path in checksScheduled:
			checksScheduled.remove(self.original_path)

		self.window.show_input_panel('Enter new name', self.original_name, self.rename, None, None)

	def rename(self, new_name):
		def action():
			def execute(files):
				RemoteSyncRename(self.original_path, getConfigFile(self.original_path), new_name).start()

			fillPasswords([[ self.original_path, getConfigFile(self.original_path) ]], execute, sublime.active_window())

		new_path = os.path.join(os.path.dirname(self.original_path), new_name)
		if os.path.exists(new_path):
			def sync(index):
				if index is 0:
					printMessage("Renaming: overwriting local target")
					action()
				else:
					printMessage("Renaming: keeping original")

			overwrite = []
			overwrite.append("Overwrite local file? Already exists in:")
			overwrite.append("Path: " + new_path)

			cancel = []
			cancel.append("Cancel renaming")
			cancel.append("")

			sublime.set_timeout(lambda: sublime.active_window().show_quick_panel([ overwrite, cancel ], sync), 1)
		else:
			action()


# Removes given file(s) or folders
class FtpSyncDelete(sublime_plugin.WindowCommand):
	def run(self, edit, paths):
		filelist = []
		for path in paths:
			filelist.append( [ path, getConfigFile(path) ] )

		def execute(files):
			RemoteSyncDelete(paths).start()

		fillPasswords(filelist, execute, sublime.active_window())

# Remote ftp navigation
class FtpSyncBrowse(sublime_plugin.WindowCommand):
	def run(self, edit = None):
		if hasActiveView() is False:
			file_path = os.path.dirname(guessConfigFile(sublime.active_window().folders()))
		else:
			file_path = os.path.dirname(sublime.active_window().active_view().file_name())

		def execute(files):
			command = SyncNavigator(None, getConfigFile(file_path), None, file_path)
			call = RemoteNavigator(getConfigFile(file_path))
			call.setCommand(command)
			call.start()

		fillPasswords([[ file_path, getConfigFile(file_path) ]], execute, sublime.active_window())

# Remote ftp navigation
class FtpSyncBrowsePlace(sublime_plugin.WindowCommand):
	def run(self, edit = None, paths = None):
		if os.path.isdir(paths[0]):
			file_path = paths[0]
		else:
			file_path = os.path.dirname(paths[0])

		def execute(files):
			command = SyncNavigator(None, getConfigFile(file_path), None, file_path)
			call = RemoteNavigator(getConfigFile(file_path))
			call.setCommand(command)
			call.start()

		fillPasswords([[ file_path, getConfigFile(file_path) ]], execute, sublime.active_window())

# Remote ftp navigation from current file
class FtpSyncBrowseCurrent(sublime_plugin.TextCommand):
	def run(self, edit = None):
		if hasActiveView() is False:
			file_path = os.path.dirname(guessConfigFile(sublime.active_window().folders()))
		else:
			file_path = sublime.active_window().active_view().file_name()

		def execute(files):
			command = SyncNavigator(os.path.dirname(file_path), getConfigFile(file_path), None, os.path.dirname(file_path))
			call = RemoteNavigator(getConfigFile(file_path))
			call.setCommand(command)
			call.start()

		fillPasswords([[ file_path, getConfigFile(file_path) ]], execute, sublime.active_window())

# Remote ftp navigation from last point
class FtpSyncBrowseLast(sublime_plugin.WindowCommand):
	def run(self, edit = None):
		if navigateLast['config_file'] is None:
			if hasActiveView() is False:
				file_path = os.path.dirname(guessConfigFile(sublime.active_window().folders()))
			else:
				file_path = sublime.active_window().active_view().file_name()

			def execute(files):
				command = SyncNavigator(None, getConfigFile(file_path), None, file_path)
				call = RemoteNavigator(getConfigFile(file_path))
				call.setCommand(command)
				call.start()


			fillPasswords([[ file_path, getConfigFile(file_path) ]], execute, sublime.active_window())
		else:
			def execute(files):
				RemoteNavigator(None, True).start()

			fillPasswords([[ None, getConfigFile(navigateLast['config_file']) ]], execute, sublime.active_window())

# Show connection info
class FtpSyncShowInfo(sublime_plugin.WindowCommand):
	def run(self, edit, paths):
		file_path = paths[0]

		def execute(files):
			ShowInfo(None, getConfigFile(file_path)).execute(sublime.active_window())

		fillPasswords([[ file_path, getConfigFile(file_path) ]], execute, sublime.active_window())

# Open FTPSync Github page
class FtpSyncUrlReadme(sublime_plugin.WindowCommand):
	def run(self):
		webbrowser.open("https://github.com/NoxArt/SublimeText2-FTPSync", 2, True)

# Open FTPSync Github New Issue page
class FtpSyncUrlReport(sublime_plugin.WindowCommand):
	def run(self):
		webbrowser.open("https://github.com/NoxArt/SublimeText2-FTPSync/issues/new", 2, True)

# Open FTPSync Donate page
class FtpSyncUrlDonate(sublime_plugin.WindowCommand):
	def run(self):
		webbrowser.open("http://ftpsync.noxart.cz/donate.html", 2, True)

# Base class for option toggling
class FTPSyncToggleSettings(sublime_plugin.TextCommand):

	def run(self, edit):
		config_file_path = getConfigFile(self.view.file_name())
		if config_file_path is None:
			return printMessage("No config file found")

		overrideConfig(config_file_path, self.property_name, self.property_value_from)

	def is_visible(self):
		if self.view is None or self.view.file_name() is None:
			return False

		config_file_path = getConfigFile(self.view.file_name())
		if config_file_path is None:
			return False

		config = loadConfig(config_file_path)

		for name in config['connections']:
			if config['connections'][name]['upload_on_save'] is self.property_value_to:
				return True

		return False

# Alters overrideConfig to enable upload_on_save
class FtpSyncEnableUos(FTPSyncToggleSettings):
	property_name = 'upload_on_save'
	property_value_from = True
	property_value_to = False

# Alters overrideConfig to disable upload_on_save
class FtpSyncDisableUos(FTPSyncToggleSettings):
	property_name = 'upload_on_save'
	property_value_from = False
	property_value_to = True

class FtpSyncCleanup(sublime_plugin.WindowCommand):
	def run(self, edit, paths):
		self.files = []
		for path in paths:
			self.files.extend(gatherMetafiles('*.ftpsync.temp', path))

		self.prompt()

	def prompt(self):
		if len(self.files) == 0:
			printMessage("No temporary files found")
			return

		toRemove = []
		toRemove.append("Remove these temporary files?")
		for path in self.files:
			toRemove.append(os.path.join(os.path.dirname(path), os.path.basename(path)))

		cancel = []
		cancel.append("Cancel removal")
		for path in self.files:
			cancel.append("")

		sublime.set_timeout(lambda: sublime.active_window().show_quick_panel([ toRemove, cancel ], self.remove), 1)

	def remove(self, index):
		if hasattr(self, 'files') and index == 0:
			for path in self.files:
				os.remove(path)
				printMessage("Removed tempfile: " + path)

