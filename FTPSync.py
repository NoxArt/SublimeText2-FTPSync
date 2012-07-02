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
import copy

# FTPSync libraries
from ftpsyncwrapper import CreateConnection
from ftpsyncprogress import Progress
from ftpsyncfiles import getFolders, findFile, getFiles, formatTimestamp


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
# time format settings
time_format = settings.get('time_format')

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
        message += " [" + str(name) + "]"

    message += " > "
    message += str(text)

    if isDebug and (onlyVerbose is False or isDebugVerbose is True):
        print message

    if status:
        dumpMessage(message)


# ==== Config =============================================================================

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
        return "Config entry 'username' must be null or string, " + str(type(config['username'])) + " given"

    if config['password'] is not None and type(config['password']) is not str and type(config['password']) is not unicode:
        return "Config entry 'password' must be null or string, " + str(type(config['password'])) + " given"

    if config['private_key'] is not None and type(config['private_key']) is not str and type(config['private_key']) is not unicode:
        return "Config entry 'private_key' must be null or string, " + str(type(config['private_key'])) + " given"

    if config['private_key_pass'] is not None and type(config['private_key_pass']) is not str and type(config['private_key_pass']) is not unicode:
        return "Config entry 'private_key_pass' must be null or string, " + str(type(config['private_key_pass'])) + " given"

    if config['ignore'] is not None and type(config['ignore']) is not str and type(config['ignore']) is not unicode:
        return "Config entry 'ignore' must be null or string, " + str(type(config['ignore'])) + " given"

    if type(config['path']) is not str and type(config['path']) is not unicode:
        return "Config entry 'path' must be a string, " + str(type(config['path'])) + " given"

    if type(config['tls']) is not bool:
        return "Config entry 'tls' must be true or false, " + str(type(config['tls'])) + " given"

    if type(config['passive']) is not bool:
        return "Config entry 'passive' must be true or false, " + str(type(config['passive'])) + " given"

    if type(config['upload_on_save']) is not bool:
        return "Config entry 'upload_on_save' must be true or false, " + str(type(config['upload_on_save'])) + " given"

    if type(config['check_time']) is not bool:
        return "Config entry 'check_time' must be true or false, " + str(type(config['check_time'])) + " given"

    if type(config['download_on_open']) is not bool:
        return "Config entry 'download_on_open' must be true or false, " + str(type(config['download_on_open'])) + " given"

    if type(config['port']) is not int:
        return "Config entry 'port' must be an integer, " + str(type(config['port'])) + " given"

    if type(config['timeout']) is not int:
        return "Config entry 'timeout' must be an integer, " + str(type(config['timeout'])) + " given"

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

        if len(connections[hash]) < len(config['connections']):
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

    if hash not in connections:
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
#
# @type file_path: string
# @type config_file_path: string
# @type onSave: bool
# @param onSave: whether this is a regular upload or upload on save
# @type disregardIgnore: bool
# @type progress: Progress
# @type whitelistConnections: list<connection_name: string>
# @param whitelistConnections: if not empty then only these connection names can be used
#
# @return [{ connection: string (connection_name), metadata: Metafile }]
def getRemoteMetadata(file_path, config_file_path, whitelistConnections=[]):
    config = loadConfig(config_file_path)
    basename = os.path.basename(file_path)

    if ignore is not None and re_ignore.search(file_path) is not None:
        return []

    config_hash = getFilepathHash(config_file_path)
    connections = getConnection(config_hash, config)

    usingConnections.append(config_hash)

    index = -1
    failed = False
    results = []

    for name in config['connections']:
        index += 1

        if len(whitelistConnections) > 0 and name not in whitelistConnections:
            continue

        try:
            connections[index]
        except IndexError:
            continue

        try:
            metadata = connections[index].list(file_path)

            if len(metadata) > 0:
                results.append({
                    'connection': name,
                    'metadata': metadata[0]
                })

        except Exception, e:
            message = "getting metadata failed: (" + basename + ") <Exception: " + str(e) + ">"

            printMessage(message, name, False, True)


    if config_hash in usingConnections:
        usingConnections.remove(config_hash)

    return results


# ==== Executive functions ======================================================================

# --- Following section could use a pretty big overhaul ---


# Uploads given file
#
# @type file_path: string
# @type config_file_path: string
# @type onSave: bool
# @param onSave: whether this is a regular upload or upload on save
# @type disregardIgnore: bool
# @type progress: Progress
# @type whitelistConnections: list<connection_name: string>
# @param whitelistConnections: if not empty then only these connection names can be used
def performSync(file_path, config_file_path, onSave, disregardIgnore=False, progress=None, whitelistConnections=[]):
    if progress is not None:
        progress.progress()

    config = loadConfig(config_file_path)
    basename = os.path.basename(file_path)

    if disregardIgnore is False and ignore is not None and re_ignore.search(file_path) is not None:
        return printMessage("file globally ignored: " + basename, onlyVerbose=True)

    config_hash = getFilepathHash(config_file_path)
    connections = getConnection(config_hash, config)

    usingConnections.append(config_hash)

    index = -1
    stored = []
    failed = False
    index = -1

    for name in config['connections']:
        index += 1

        if len(whitelistConnections) > 0 and name not in whitelistConnections:
            continue

        try:
            connections[index]
        except IndexError:
            continue

        if config['connections'][name]['upload_on_save'] is False and onSave is True:
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

            printMessage("performSync exception: " + str(e))

        if failed:
            message = "upload failed: (" + basename + ")"

            if type(failed) is Exception:
                message += "<Exception: " + str(failed) + ">"

            printMessage(message, name, False, True)

    if len(stored) > 0:
        dumpMessage(getProgressMessage(stored, progress, "uploaded", basename))

    if config_hash in usingConnections:
        usingConnections.remove(config_hash)


# Renames given file
def performSyncRename(file_path, config_file, new_name):
    config = loadConfig(config_file)
    basename = os.path.basename(file_path)
    dirname = os.path.dirname(file_path)
    config_hash = getFilepathHash(config_file)
    connections = getConnection(config_hash, config)

    usingConnections.append(config_hash)

    index = -1
    failed = False

    for name in config['connections']:
        index += 1

        try:
            connections[index]
        except IndexError:
            continue

        try:
            uploaded = connections[index].rename(file_path, new_name)

            if type(uploaded) is str or type(uploaded) is unicode:
                printMessage("renamed " + basename + " -> " + new_name, name)
            else:
                failed = type(uploaded)

            os.rename(file_path, os.path.join(dirname, new_name))

        except Exception, e:
            failed = e

            printMessage("performSyncRename exception: " + str(e))

        if failed:
            message = "renaming failed: (" + basename + " -> " + new_name + ")"

            if type(failed) is Exception:
                message += "<Exception: " + str(failed) + ">"

            printMessage(message, name, False, True)

    # rename file
    os.rename(file_path, os.path.join(dirname, new_name))

    if config_hash in usingConnections:
        usingConnections.remove(config_hash)


# Downloads given file
#
# @type file_path: string
# @type config_file_path: string
# @type disregardIgnore: bool
# @type progress: Progress
# @type isDir: bool
# @param isDir: whether the downloaded entry is a folder
# @type forced: bool
# @param forced: whether it should download even if older or same size
# @type skip: bool
# @param skip: used with forced=False, should skip the download (the rest is needed though, for progress etc.)
# @type whitelistConnections: list<connection_name: string>
# @param whitelistConnections: if not empty then only these connection names can be used
def performSyncDown(file_path, config_file_path, disregardIgnore=False, progress=None, isDir=None,forced=False,skip=False, whitelistConnections=[]):
    if progress is not None and isDir is not True:
        progress.progress()

    config = loadConfig(config_file_path)
    basename = os.path.basename(file_path)

    if disregardIgnore is False and ignore is not None and re_ignore.search(file_path) is not None:
        return printMessage("file globally ignored: " + basename, onlyVerbose=True)

    config_hash = getFilepathHash(config_file_path)
    connections = getConnection(config_hash, config)

    usingConnections.append(config_hash)

    index = -1
    stored = []
    failed = False

    for name in config['connections']:
        index += 1

        if len(whitelistConnections) > 0 and name not in whitelistConnections:
            continue

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
                    if entry.isDirectory() is False:
                        progress.add([entry.getName()])

                for entry in contents:
                    full_name = os.path.join(file_path, entry.getName())

                    if entry.isDirectory() is True:
                        performSyncDown(full_name, config_file_path, disregardIgnore, progress, True, forced=forced)
                    else:
                        completed = False

                        if not forced and entry.isNewerThan(full_name) is False:
                            completed = True

                        performSyncDown(full_name, config_file_path, disregardIgnore, progress, forced=forced, skip=completed)

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

            printMessage("performSyncDown exception: " + str(e))

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


def performRemoteCheck(file_path, window, forced=False):
    if type(file_path) is not str and type(file_path) is not unicode:
        return

    if window is None:
        return

    printMessage("Checking " + os.path.basename(file_path) + " if up-to-date", status=True)

    config_file_path = getConfigFile(file_path)
    if config_file_path is None:
        return printMessage("Found no config > for file: " + file_path, status=forced)

    config = loadConfig(config_file_path)
    checking = []

    if forced is False:
        for name in config['connections']:
            if config['connections'][name]['download_on_open'] is True:
                checking.append(name)

        if len(checking) is 0:
            return

    try:
        metadata = getRemoteMetadata(file_path, config_file_path, checking)
    except:
        metadata = []

    if len(metadata) == 0:
        return printMessage("No version found on any server", status=True)

    newest = []
    oldest = []
    every = []
    extra = []

    for entry in metadata:
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

        def sync(index):
            if index > 0:
                if isDebug:
                    i = 0
                    for entry in every:
                        printMessage("Listing connection " + str(i) + ": " + str(entry['connection']))
                        i += 1

                    printMessage("Index selected: " + str(index - 1))

                RemoteSyncDownCall(file_path, getConfigFile(file_path), True, whitelistConnections=[every[index - 1]['connection']]).start()

        filesize = os.path.getsize(file_path)
        items = ["Keep current (" + str(round(float(os.path.getsize(file_path)) / 1024, 3)) + " kB | " + formatTimestamp(os.path.getmtime(file_path)) + ")"]
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

            time = str(item['metadata'].getLastModifiedFormatted(time_format))

            if item in newest:
                time += " ~ newer"
            else:
                time += " ~ older"

            items.append(["Get from <" + item['connection'] + "> (" + item_filesize + " | " + time + ")"])
            index += 1

        sublime.set_timeout(lambda: window.show_quick_panel(items, sync), 1)
    else:
        printMessage("All remote versions are of same size and older", status=True)



# ==== Watching ===========================================================================

# File watching
class RemoteSync(sublime_plugin.EventListener):

    # @todo - put into thread
    def on_pre_save(self, view):
        file_path = view.file_name()
        config_file_path = getConfigFile(file_path)
        if config_file_path is None:
            return

        config = loadConfig(config_file_path)
        metadata = getRemoteMetadata(file_path, config_file_path)

        newest = None
        newer = []
        index = 0

        for entry in metadata:
            if config['connections'][ entry['connection'] ]['check_time'] is True and entry['metadata'].isNewerThan(file_path):
                skipped = True
                newer.append(entry['connection'])

                if newest is None or newest > entry['metadata'].getLastModified():
                    newest = index

            index += 1

        if len(newer) > 0:
            def sync(index):
                if index is 1:
                    self.on_post_save(view)

            items = [
                "Newer entry in <" + ','.join(newer) + "> - cancel upload?",
                "Overwrite, newest: " + metadata[newest]['metadata'].getLastModifiedFormatted()
            ]

            window = view.window()
            if window is None:
                window = sublime.active_window() # only in main thread!

            sublime.set_timeout(lambda: window.show_quick_panel(items, sync), 1)

    def on_post_save(self, view):
        file_path = view.file_name()
        RemoteSyncCall(file_path, getConfigFile(file_path), True).start()

    def on_close(self, view):
        config_file_path = getConfigFile(view.file_name())

        if config_file_path is not None:
            closeConnection(getFilepathHash(config_file_path))

    # When a file is loaded and at least 1 connection has download_on_open enabled
    # it will check those enabled if the remote version is newer and offers the newest to download
    def on_load(self, view):
        RemoteSyncCheck(view.file_name(), view.window()).start()



# ==== Threading ===========================================================================

def fillProgress(progress, entry):
    if type(entry) is list:
        for item in entry:
            fillProgress(progress, item)
    elif os.path.isfile(entry):
        progress.add([entry])

class RemoteSyncCall(threading.Thread):
    def __init__(self, file_path, config, onSave, disregardIgnore=False, whitelistConnections=[]):
        self.file_path = file_path
        self.config = config
        self.onSave = onSave
        self.disregardIgnore = disregardIgnore
        self.whitelistConnections = whitelistConnections
        threading.Thread.__init__(self)

    def run(self):
        target = self.file_path

        if (type(target) is str or type(target) is unicode) and self.config is None:
            return False

        if type(target) is str or type(target) is unicode:
            performSync(target, self.config, self.onSave, self.disregardIgnore, whitelistConnections=self.whitelistConnections)
        elif type(target) is list:
            total = len(target)
            progress = Progress(total)
            fillProgress(progress, target)

            for file_path, config in target:
                performSync(file_path, config, self.onSave, self.disregardIgnore, progress, whitelistConnections=self.whitelistConnections)


class RemoteSyncDownCall(threading.Thread):
    def __init__(self, file_path, config, disregardIgnore=False,forced=False,whitelistConnections=[]):
        self.file_path = file_path
        self.config = config
        self.disregardIgnore = disregardIgnore
        self.forced = forced
        self.whitelistConnections=[]
        threading.Thread.__init__(self)

    def run(self):
        target = self.file_path

        if (type(target) is str or type(target) is unicode) and self.config is None:
            return False

        if type(target) is str or type(target) is unicode:
            performSyncDown(target, self.config, self.disregardIgnore, forced=self.forced, whitelistConnections=self.whitelistConnections)
        else:
            total = len(target)
            progress = Progress(total)

            for file_path, config in target:
                if os.path.isfile(file_path):
                    progress.add([file_path])

                performSyncDown(file_path, config, self.disregardIgnore, progress, forced=self.forced, whitelistConnections=self.whitelistConnections)


class RemoteSyncRename(threading.Thread):
    def __init__(self, file_path, config, new_name):
        self.file_path = file_path
        self.new_name = new_name
        self.config = config
        threading.Thread.__init__(self)

    def run(self):
        performSyncRename(self.file_path, self.config, self.new_name)


class RemoteSyncCheck(threading.Thread):
    def __init__(self, file_path, window, forced=False):
        self.file_path = file_path
        self.window = window
        self.forced = forced
        threading.Thread.__init__(self)

    def run(self):
        performRemoteCheck(self.file_path, self.window, self.forced)



# ==== Commands ===========================================================================

# Sets up a config file in a directory
class FtpSyncNewSettings(sublime_plugin.TextCommand):
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
class FtpSyncCurrent(sublime_plugin.TextCommand):
    def run(self, edit):
        file_path = sublime.active_window().active_view().file_name()

        RemoteSyncCall(file_path, getConfigFile(file_path), False).start()


# Synchronize down current file
class FtpSyncDownCurrent(sublime_plugin.TextCommand):
    def run(self, edit):
        file_path = sublime.active_window().active_view().file_name()

        RemoteSyncDownCall(file_path, getConfigFile(file_path), False, True).start()


# Checks whether there's a different version of the file on server
class FtpSyncCheckCurrent(sublime_plugin.TextCommand):
    def run(self, edit):
        file_path = sublime.active_window().active_view().file_name()
        view = sublime.active_window()

        RemoteSyncCheck(file_path, view, True).start()


# Synchronize down selected file/directory
class FtpSyncDownTarget(sublime_plugin.TextCommand):
    def run(self, edit, paths, forced=False):
        RemoteSyncDownCall(getFiles(paths, getConfigFile), None, forced=forced).start()


# Renames a file on disk and in folder
class FtpSyncRename(sublime_plugin.TextCommand):
    def run(self, edit, paths):
        self.original_path = paths[0]
        self.folder = os.path.dirname(self.original_path)
        self.original_name = os.path.basename(self.original_path)

        self.view.window().show_input_panel('Enter new name', self.original_name, self.rename, None, None)

    def rename(self, new_name):
        RemoteSyncRename(self.original_path, getConfigFile(self.original_path), new_name).start()


# Removes given file(s) or folders
class FtpSyncDelete(sublime_plugin.TextCommand):
    def run(self, edit, paths):
        pass
