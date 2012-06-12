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

# Sublime API see http://www.sublimetext.com/docs/2/api_reference.html
import sublime
import sublime_plugin

# Python's built-in libraries
import shutil
import os
import hashlib
import json
import threading
import re

# FTPSync libraries
from ftpsyncwrapper import CreateConnection
from ftpsyncprogress import Progress


# ==== Initialization and optimization =====================================================

# global config
settings = sublime.load_settings('ftpsync.sublime-settings')


# print debug messages to console?
isDebug = settings.get('debug')
# print overly informative messages?
isDebugVerbose = settings.get('debug_verbose')
# default config for a project
projectDefaults = settings.get('project_defaults').items()
# global ignore pattern
ignore = settings.get('ignore')


# loaded project's config will be merged with this global one
coreConfig = {
    'ignore': ignore,
    'connection_timeout': settings.get('connection_timeout')
}.items()

# compiled global ignore pattern
if type(ignore) is str or type(ignore) is unicode:
    re_ignore = re.compile(ignore)
else:
    re_ignore = None


# name of a file to be detected in the project
configName = 'ftpsync.settings'
# name of a file that is a default sheet for new configs for projects
connectionDefaultsFilename = 'ftpsync.default-settings'
# timeout for a Sublime status bar messages [ms]
messageTimeout = 250
# limit for breaking down a filepath structure when looking for config files
nestingLimit = 30
# difference in time when comes to local vs remote {last modified} [s]
timeDifferenceTolerance = 2
# comment removing regexp
removeLineComment = re.compile('//.*', re.I)


# connection cache pool - all connections
connections = {}
# connections currently marked as {in use}
usingConnections = []
# individual folder config cache, file => config path
configs = {}


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
        print message

    if status:
        dumpMessage(message)


# ==== File&folders ========================================================================

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
#
# @return list<string> of file paths
def getFiles(paths):
    files = []
    fileNames = []

    for target in paths:
        if target not in fileNames:
            files.append([target, getConfigFile(target)])

    return files


# ==== Config =============================================================================

# Invalidates all config cache entries belonging to a certain directory
# as long as they're empty or less nested in the filesystem
#
# @type  config_dir_name: string
# @param config_dir_name: path to a folder of a config to be invalidated
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
def findConfigFile(folders):
    return findFile(folders, configName)


# Returns configuration file for a given file
#
# @type  file_path: string
# @param file_path: file_path to the file for which we try to find a config
#
# @return file path to the config file or None
#
# @global configs
def getConfigFile(file_path):
    # try cached
    try:
        if configs[file_path]:
            printMessage("Loading config: cache hit (key: " + file_path + ")")

        return configs[file_path]

    # cache miss
    except KeyError:
        try:
            folders = getFolders(file_path)

            if folders is None or len(folders) == 0:
                return None

            configFolder = findConfigFile(folders)

            if configFolder is None:
                return printMessage("Found no config > for file: " + file_path)

            config = os.path.join(configFolder, configName)
            configs[file_path] = config
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
    return hashlib.md5(file_path).hexdigest()


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

    keys = ["username", "password", "private_key", "private_key_pass", "path", "tls", "upload_on_save", "port", "timeout", "ignore", "check_time", "download_on_open"]

    for key in keys:
        if key not in config:
            return "Config is missing a {" + key + "} key"

    if config['username'] is not None and type(config['username']) is not str and type(config['username']) is not unicode:
        return "Username must be null or string"

    if config['password'] is not None and type(config['password']) is not str and type(config['password']) is not unicode:
        return "Password must be null or string"

    if config['private_key'] is not None and type(config['private_key']) is not str and type(config['private_key']) is not unicode:
        return "Private_key must be null or string"

    if config['private_key_pass'] is not None and type(config['private_key_pass']) is not str and type(config['private_key_pass']) is not unicode:
        return "Private_key_pass must be null or string"

    if config['ignore'] is not None and type(config['ignore']) is not str and type(config['ignore']) is not unicode:
        return "Ignore must be null or string"

    if type(config['path']) is not str and type(config['path']) is not unicode:
        return "Path must be a string"

    if type(config['tls']) is not bool:
        return "Tls must be bool"

    if type(config['upload_on_save']) is not bool:
        return "Upload_on_save must be bool"

    if type(config['check_time']) is not bool:
        return "Check_time must be bool"

    if type(config['download_on_open']) is not bool:
        return "Download_on_open must be bool"

    if type(config['port']) is not int:
        return "Port must be an integer"

    if type(config['timeout']) is not int:
        return "Timeout must be an integer"

    return True


# Parses JSON-type file with comments stripped out (not part of a proper JSON, see http://json.org/)
#
# @type  file_path: string
#
# @return dict
def parseJson(file_path):
    contents = ""
    file = open(file_path, 'r')

    for line in file:
        contents += removeLineComment.sub('', line)

    file.close()

    return json.loads(contents)


# Parses given config and adds default values to each connection entry
#
# @type  file_path: string
# @param file_path: file path to the file of which we want the hash
#
# @return config dict or None
#
# @global coreConfig
# @global projectDefaults
def loadConfig(file_path):
    if os.path.exists(file_path) is False:
        return None

    # parse config
    try:
        config = parseJson(file_path)
    except Exception, e:
        printMessage("Failed parsing configuration file: " + file_path + " (commas problem?) <Exception: " + str(e) + ">", status=True)
        return None

    result = {}

    # merge with defaults and check
    for name in config:
        result[name] = dict(projectDefaults + config[name].items())
        result[name]['file_path'] = file_path

        verification_result = verifyConfig(result[name])

        if verification_result is not True:
            printMessage("Invalid configuration loaded: <" + str(verification_result) + ">",status=True)

    # merge with generics
    final = dict(coreConfig + {"connections": result}.items())

    return final


# ==== Remote =============================================================================

# Returns connection, connects if needed
#
# @type  hash: string
# @param hash: connection cache hash (config filepath hash actually)
# @type  config: object
# @param config: configuration object
#
# @return dict of descendants of AbstractConnection (ftpsyncwrapper.py)
#
# @global connections
def getConnection(hash, config):
    # try cache
    try:
        if connections[hash] and len(connections[hash]) > 0:
            printMessage("Connection cache hit (key: " + hash + ")", None, True)

        if len(connections[hash]) == 0:
            raise KeyError

        return connections[hash]

    # cache miss
    except KeyError:
        connections[hash] = []

        # for each config
        for name in config['connections']:
            properties = config['connections'][name]

            # 1. initialize
            try:
                connection = CreateConnection(properties, name)
            except Exception, e:
                printMessage("Connection initialization failed <Exception: " + str(e) + ">", name, status=True)

                continue

            # 2. connect
            try:
                connection.connect()
            except Exception, e:
                printMessage("Connection failed <Exception: " + str(e) + ">", name, status=True)
                connection.close(connection, hash)

                continue

            printMessage("Connected to: " + properties['host'] + ":" + str(properties['port']) + " (timeout: " + str(properties['timeout']) + ") (key: " + hash + ")", name)

            # 3. authenticate
            try:
                if connection.authenticate():
                    printMessage("Authentication processed", name)
            except Exception, e:
                printMessage("Authentication failed <Exception: " + str(e) + ">", name, status=True)

                continue

            # 4. login
            if properties['username'] is not None:
                try:
                    connection.login()
                except Exception, e:
                    printMessage("Login failed <Exception: " + str(e) + ">", name, status=True)

                    continue

                pass_present = " (using password: NO)"
                if len(properties['password']) > 0:
                    pass_present = " (using password: YES)"

                printMessage("Logged in as: " + properties['username'] + pass_present, name)
            else:
                printMessage("Anonymous connection", name)

            # 5. set initial directory, set name, store connection
            try:
                connection.cwd(properties['path'])
            except Exception, e:
                printMessage("Failed to set path (probably connection failed) <Exception: " + str(e) + ">", name)

                continue

            # 6. add to connectins list
            present = False
            for con in connections[hash]:
                if con.name == connection.name:
                    present = True

            if present is False:
                connections[hash].append(connection)


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
    if type(hash) is not str and type(hash) is not unicode:
        printMessage("Error closing connection: connection hash must be a string, " + str(type(hash)) + " given")
        return

    try:
        for connection in connections[hash]:
            connection.close(connections, hash)
            printMessage("closed", connection.name)

        if len(connections[hash]) == 0:
            connections.pop(hash)

    except Exception, e:
        printMessage("Error when closing connection (key: " + hash + ") <Exception: " + str(e) + ">")


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
def getProgressMessage(stored, progress, action, basename):
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

    return base + action + basename


# Uploads given file
def performSync(file_path, config_file, onSave, disregardIgnore=False, progress=None):
    if progress is not None:
        progress.progress()

    config = loadConfig(config_file)
    basename = os.path.basename(file_path)

    if disregardIgnore is False and ignore is not None and re_ignore.search(file_path) is not None:
        return printMessage("file globally ignored: " + basename, onlyVerbose=True)

    config_hash = getFilepathHash(config_file)
    connections = getConnection(config_hash, config)

    usingConnections.append(config_hash)

    index = -1
    stored = []
    failed = False

    for name in config['connections']:
        index += 1

        try:
            connections[index]
        except IndexError:
            continue

           # legacy check
        if 'upload_on_save' in config['connections'][name] and config['connections'][name]['upload_on_save'] is False and onSave is True:
            return

        if disregardIgnore is False and config['connections'][name]['ignore'] is not None and re.search(config['connections'][name]['ignore'], file_path):
            printMessage("file ignored by rule: " + basename, name, True)
            break

        try:
            uploaded = connections[index].put(file_path)

            if type(uploaded) is str or type(uploaded) is unicode:
                stored.append(uploaded)
                printMessage("uploaded " + basename, name)

            else:
                failed = type(uploaded)

        except Exception, e:
            failed = e

            print e

        if failed:
            message = "upload failed: (" + basename + ")"

            if type(failed) is Exception:
                message += "<Exception: " + str(failed) + ">"

            printMessage(message, name, False, True)

    if len(stored) > 0:
        dumpMessage(getProgressMessage(stored, progress, "uploaded", basename))

    if config_hash in usingConnections:
        usingConnections.remove(config_hash)


# Downloads given file
def performSyncDown(file_path, config_file, disregardIgnore=False, progress=None, isDir=None,forced=False,skip=False):
    if progress is not None and isDir is not True:
        progress.progress()

    config = loadConfig(config_file)
    basename = os.path.basename(file_path)

    if disregardIgnore is False and ignore is not None and re_ignore.search(file_path) is not None:
        return printMessage("file globally ignored: " + basename, onlyVerbose=True)

    config_hash = getFilepathHash(config_file)
    connections = getConnection(config_hash, config)

    usingConnections.append(config_hash)

    index = -1
    stored = []
    failed = False

    for name in config['connections']:
        index += 1

        try:
            connections[index]
        except IndexError:
            continue

        if disregardIgnore is False and config['connections'][name]['ignore'] is not None and re.search(config['connections'][name]['ignore'], file_path):
            printMessage("file ignored by rule: " + basename, name, True)
            continue

        try:

            contents = connections[index].list(file_path)

            if isDir or os.path.isdir(file_path):
                if os.path.exists(file_path) is False:
                    os.mkdir(file_path)

                for entry in contents:
                    if entry['isDir'] is False:
                        progress.add([entry['name']])

                for entry in contents:
                    if entry['isDir'] is True:
                        performSyncDown(os.path.join(file_path, entry['name']), config_file, disregardIgnore, progress, True, forced=forced)
                    else:
                        completed = False

                        if not forced and compareFilesDirect(os.path.join(file_path, entry['name']), entry, True, True) is False:
                            completed = True

                        performSyncDown(os.path.join(file_path, entry['name']), config_file, disregardIgnore, progress, forced=forced, skip=completed)

                return
            else:
                if skip:
                    downloaded = name
                else:
                    downloaded = connections[index].get(file_path)

            if type(downloaded) is str or type(downloaded) is unicode:
                stored.append(downloaded)
                printMessage("downloaded " + basename, name)

            else:
                failed = type(downloaded)

        except Exception, e:
            failed = e

            print file_path + " => " + str(e)

        if failed:
            message = "download failed: (" + basename + ")"

            if type(failed) is Exception:
                message += "<Exception: " + str(failed) + ">"

            printMessage(message, name, False, True)
        else:
            break

    if len(stored) > 0:
        dumpMessage(getProgressMessage(stored, progress, "downloaded", basename))

    if config_hash in usingConnections:
        usingConnections.remove(config_hash)


def compareFilesDirect(file_path, properties, newer, larger, both=False):
    if os.path.exists(file_path) is False:
        return True

    lastModified = os.path.getmtime(file_path)
    filesize = os.path.getsize(file_path)

    isNewer = lastModified - properties['lastModified'] < timeDifferenceTolerance
    isDifferentSize = properties['filesize'] != filesize

    if both and isNewer and isDifferentSize:
        return True

    if not both and newer and isNewer:
        return True

    if not both and larger and isDifferentSize:
        return True

    return False


# File watching
class RemoteSync(sublime_plugin.EventListener):
    def on_post_save(self, view):
        file_path = view.file_name()
        RemoteSyncCall(file_path, getConfigFile(file_path), True).start()

    def on_close(self, view):
        config_file = getConfigFile(view.file_name())

        if config_file is not None:
            hash = getFilepathHash(config_file)
            closeConnection(hash)


# Remote handling
class RemoteSyncCall(threading.Thread):
    def __init__(self, file_path, config, onSave, disregardIgnore=False):
        self.file_path = file_path
        self.config = config
        self.onSave = onSave
        self.disregardIgnore = disregardIgnore
        threading.Thread.__init__(self)

    def run(self):
        target = self.file_path

        if (type(target) is str or type(target) is unicode) and self.config is None:
            return False

        if type(target) is str or type(target) is unicode:
            performSync(target, self.config, self.onSave, self.disregardIgnore)
        elif type(target) is list:
            total = len(target)
            progress = Progress(total)

            for file_path, config in target:
                performSync(file_path, config, self.onSave, self.disregardIgnore, progress)


# Remote handling
class RemoteSyncDownCall(threading.Thread):
    def __init__(self, file_path, config, disregardIgnore=False,forced=False):
        self.file_path = file_path
        self.config = config
        self.disregardIgnore = disregardIgnore
        self.forced = forced
        threading.Thread.__init__(self)

    def run(self):
        target = self.file_path

        if (type(target) is str or type(target) is unicode) and self.config is None:
            return False

        if type(target) is str or type(target) is unicode:
            performSyncDown(target, self.config, self.disregardIgnore, forced=self.forced)
        else:
            total = len(target)
            progress = Progress(total)

            for file_path, config in target:
                if os.path.isfile(file_path):
                    progress.add([file_path])

                performSyncDown(file_path, config, self.disregardIgnore, progress, forced=self.forced)


# Sets up a config file in a directory
class NewFtpSyncCommand(sublime_plugin.TextCommand):
    def run(self, edit, dirs):
        if len(dirs) == 0:
            dirs = [os.path.dirname(self.view.file_name())]

        default = os.path.join(sublime.packages_path(), 'FTPSync', connectionDefaultsFilename)

        for directory in dirs:
            config = os.path.join(directory, configName)

            invalidateConfigCache(directory)

            if os.path.exists(config) is True:
                self.view.window().open_file(config)
            else:
                shutil.copyfile(default, config)
                self.view.window().open_file(config)


# Synchronize up selected file/directory
class FtpSyncTarget(sublime_plugin.TextCommand):
    def run(self, edit, paths):
        syncFiles = []
        fileNames = []

        # gather files
        for target in paths:
            if os.path.isfile(target):
                if target not in fileNames:
                    syncFiles.append([target, getConfigFile(target)])
            elif os.path.isdir(target):
                for root, dirs, files in os.walk(target):
                    for file_path in files:
                        if file_path not in fileNames:
                            syncFiles.append([root + "\\" + file_path, getConfigFile(root + "\\" + file_path)])

        # sync
        RemoteSyncCall(syncFiles, None, False).start()


# Synchronize up current file
class SyncCurrent(sublime_plugin.TextCommand):
    def run(self, edit):
        file_path = sublime.active_window().active_view().file_name()

        RemoteSyncCall(file_path, getConfigFile(file_path), False).start()


# Synchronize down current file
class SyncDownCurrent(sublime_plugin.TextCommand):
    def run(self, edit):
        file_path = sublime.active_window().active_view().file_name()

        RemoteSyncDownCall(file_path, getConfigFile(file_path), False, True).start()


# Synchronize down selected file/directory
class FtpSyncDownTarget(sublime_plugin.TextCommand):
    def run(self, edit, paths, forced=False):
        RemoteSyncDownCall(getFiles(paths), None, forced=forced).start()
