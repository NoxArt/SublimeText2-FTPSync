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

import sublime
import sublime_plugin
import shutil
import os
import hashlib
import json
import threading
import re
from math import ceil
from ftpsyncwrapper import CreateConnection

# Init

# global config
settings = sublime.load_settings('ftpsync.sublime-settings')

isDebug = settings.get('debug')  # print debug messages to console?
isDebugVerbose = settings.get('debug_verbose')  # print overly informative messages?
projectDefaults = settings.get('project_defaults')  # default config for a project
ignore = settings.get('ignore')  # global ignore pattern

# loaded project's config will be merged with this global one
coreConfig = {
    'ignore': ignore,
    'connection_timeout': settings.get('connection_timeout')
}

# compiled global ignore pattern
re_ignore = re.compile(ignore)


# storing literals
configName = 'ftpsync.settings'
defaultConnectioConfigName = 'ftpsync.sublime-settings'
messageTimeout = 250
nestingLimit = 30

# connection cache pool
connections = {}
usingConnections = []
# threads pool
threads = []
# individual folder configs, file => config path
configs = {}
# messages scheduled to be dumped to status bar
messages = []


# ==== Messaging ===========================================================================
def statusMessage(text):
    sublime.status_message(text)


def dumpMessages():
    messages.reverse()
    for message in messages:
        statusMessage(message)
        messages.remove(message)


def clearMessages():
    for message in messages:
        messages.remove(message)


def printMessage(text, name=None, onlyVerbose=False, status=False):
    message = "FTPSync"

    if name is not None:
        message += " [" + name + "]"

    message += " > "
    message += text

    if isDebug and (onlyVerbose is False or isDebugVerbose is True):
        print message

    if status:
        messages.append(message)
        sublime.set_timeout(dumpMessages, messageTimeout)


# ==== File&folders ========================================================================

def getFolders(viewOrFilename):
    if type(viewOrFilename) == str or type(viewOrFilename) == unicode:
        folders = [viewOrFilename]
        max = nestingLimit

        while True:
            split = os.path.split(viewOrFilename)
            viewOrFilename = split[0]
            max -= 1

            if len(split[1]) == 0 or max < 0:
                break

            folders.append(split[0])

        return folders
    else:
        return viewOrFilename.window().folders()


def findFile(folders, file_name):
    for folder in folders:
        if os.path.exists(os.path.join(folder, file_name)) is True:
            return folder

    return None


# ==== Config =============================================================================

# Invalidates all config cache entries belonging to a certain directory
# as long as they're empty or less nested in the filesystem
def invalidateConfigCache(config_dir_name):
    for file_name in configs:
        if file_name.startswith(config_dir_name) and (configs[file_name] is None or config_dir_name.startswith(configs[file_name])):
            configs.remove(configs[file_name])


# Finds a config file in given folders
def findConfigFile(folders):
    return findFile(folders, configName)


# Returns configuration file for a given file
def getConfigFile(file_name):
    # try cached
    try:
        if configs[file_name]:
            printMessage("Loading config: cache hit (key: " + file_name + ")")

        return configs[file_name]
    except KeyError:
        try:
            folders = getFolders(file_name)

            if folders is None or len(folders) == 0:
                return None

            configFolder = findConfigFile(folders)

            if configFolder is None:
                return printMessage("Found no config > for file: " + file_name)

            config = os.path.join(configFolder, configName)
            configs[file_name] = config
            return config

        except AttributeError:
            return None


def getConfigHash(file_name):
    return hashlib.md5(file_name).hexdigest()


# Parses given config and adds default values to each connection entry
def loadConfig(file_name):
    file = open(file_name)
    contents = ""

    for line in file:
        if line.find('//') is -1:
            contents += line

    try:
        config = json.loads(contents)
    except:
        printMessage("Failed parsing configuration file: " + file_name + " (commas problem?)", status=True)
        return None

    result = {}

    for name in config:
        result[name] = dict(projectDefaults.items() + config[name].items())
        result[name]['file_name'] = file_name

    final = dict(coreConfig.items() + {"connections": result}.items())

    return final


# ==== Remote =============================================================================

# Returns connection, connects if needed
def getConnection(hash, config):
    try:
        if connections[hash] and len(connections[hash]) > 0:
            printMessage("Connection cache hit (key: " + hash + ")", None, True)

        if len(connections[hash]) == 0:
            raise KeyError

        return connections[hash]
    except KeyError:
        connections[hash] = []

        for name in config['connections']:
            properties = config['connections'][name]

            # 1. initialize
            connection = CreateConnection(properties, name)

            # 2. connect
            try:
                connection.connect()
            except:
                printMessage("Connection failed", name, status=True)
                connection.close(hash)

            printMessage("Connected to: " + properties['host'] + ":" + str(properties['port']) + " (timeout: " + str(properties['timeout']) + ") (key: " + hash + ")", name)

            # 3. authenticate
            if connection.authenticate():
                printMessage("Authentication processed", name)

            # 4. login
            if properties['username'] is not None:
                connection.login()

                if isDebug:
                    pass_present = " (using password: NO)"
                    if len(properties['password']) > 0:
                        pass_present = " (using password: YES)"

                    printMessage("Logged in as: " + properties['username'] + pass_present, name)

            elif isDebug:
                printMessage("Anonymous connection", name)

            # 5. set initial directory, set name, store connection
            try:
                connection.cwd(properties['path'])

                present = False
                for con in connections[hash]:
                    if con.name == connection.name:
                        present = True

                if present is False:
                    connections[hash].append(connection)
            except:
                printMessage("Failed to set path (probably connection failed)", name)

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
def closeConnection(hash):
    try:
        for connection in connections[hash]:
            connection.close(connections, hash)
            printMessage("closed", connection.name)

        if len(connections[hash]) == 0:
            connections.pop(hash)

    except:
        return


# Uploads given file
def performSync(file_name, config_file, disregardIgnore=False, progress=None):
    progress.progress()
    config = loadConfig(config_file)
    basename = os.path.basename(file_name)

    if disregardIgnore is False and len(ignore) > 0 and re_ignore.search(file_name) is not None:
        return printMessage("file globally ignored: " + basename, onlyVerbose=True)

    config_hash = getConfigHash(config_file)
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

        if disregardIgnore is False and config['connections'][name]['ignore'] is not None and re.search(config['connections'][name]['ignore'], file_name):
            printMessage("file ignored by rule: " + basename, name, True)
            break

        try:
            uploaded = connections[index].put(file_name)

            if type(uploaded) is str or type(uploaded) is unicode:
                stored.append(uploaded)
                printMessage("uploaded " + basename, name)

            else:
                failed = type(uploaded)

        except Exception, e:
            failed = e

            print e

        if failed:
            printMessage("upload failed: (" + basename + ") ", name, False, True)

    if len(stored) > 0:
        base = "FTPSync [remotes: " + ",".join(stored) + "] "
        action = "> uploaded "

        if progress is not None:
            base += " ["

            percent = progress.getPercent()

            for i in range(0, int(percent)):
                base += "="
            for i in range(int(percent), 10):
                base += "--"

            base += " " + str(progress.current) + "/" + str(progress.getTotal()) + "] "

        clearMessages()
        messages.append(base + action + basename)

        sublime.set_timeout(dumpMessages, messageTimeout)

    if config_hash in usingConnections:
        usingConnections.remove(config_hash)


# Downloads given file
# DRY, man, DRY ... :/
def performSyncDown(file_name, config_file, disregardIgnore=False, progress=None, isDir=None):
    config = loadConfig(config_file)
    basename = os.path.basename(file_name)

    if disregardIgnore is False and len(ignore) > 0 and re_ignore.search(file_name) is not None:
        return printMessage("file globally ignored: " + basename, onlyVerbose=True)

    config_hash = getConfigHash(config_file)
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

        if disregardIgnore is False and config['connections'][name]['ignore'] is not None and re.search(config['connections'][name]['ignore'], file_name):
            printMessage("file ignored by rule: " + basename, name, True)
            break

        try:

            contents = connections[index].list(file_name)

            if isDir or os.path.isdir(file_name):
                if os.path.exists(file_name) is False:
                    os.mkdir(file_name)

                for entry in contents:
                    if entry['isDir'] is False:
                        progress.add([entry['name']])

                for entry in contents:
                    if entry['isDir'] is True:
                        performSyncDown(os.path.join(file_name, entry['name']), config_file, disregardIgnore, progress, True)
                    else:
                        performSyncDown(os.path.join(file_name, entry['name']), config_file, disregardIgnore, progress)

                return
            else:
                downloaded = connections[index].get(file_name)

            if type(downloaded) is str or type(downloaded) is unicode:
                stored.append(downloaded)
                printMessage("downloaded " + basename, name)

            else:
                failed = type(downloaded)

        except Exception, e:
            failed = e

            print file_name + " => " + str(e)

        if failed:
            printMessage("download failed: (" + basename + ") ", name, False, True)

    if len(stored) > 0:
        base = "FTPSync [remotes: " + ",".join(stored) + "] "
        action = "> downloaded "

        if progress is not None:
            base += " ["

            progress.progress()
            percent = progress.getPercent()

            for i in range(0, int(percent)):
                base += "="
            for i in range(int(percent), 10):
                base += "--"

            base += " " + str(progress.current) + "/" + str(progress.getTotal()) + "] "

        clearMessages()
        messages.append(base + action + basename)

        sublime.set_timeout(dumpMessages, messageTimeout)

    if config_hash in usingConnections:
        usingConnections.remove(config_hash)


# File watching
class RemoteSync(sublime_plugin.EventListener):
    def on_post_save(self, view):
        file_name = view.file_name()
        thread = RemoteSyncCall(file_name, getConfigFile(file_name))
        threads.append(thread)
        thread.start()

    def on_close(self, view):
        config_file = getConfigFile(view.file_name())

        if config_file is not None:
            hash = getConfigHash(config_file)
            closeConnection(hash)


# Remote handling
class RemoteSyncCall(threading.Thread):
    def __init__(self, file_name, config, disregardIgnore=False):
        self.file_name = file_name
        self.config = config
        self.disregardIgnore = disregardIgnore
        threading.Thread.__init__(self)

    def run(self):
        target = self.file_name

        if (type(target) is str or type(target) is unicode) and self.config is None:
            return False

        if type(target) is str or type(target) is unicode:
            performSync(target, self.config, self.disregardIgnore)
        elif type(target) is list:
            total = len(target)
            progress = Progress(total)

            for file, config in target:
                performSync(file, config, self.disregardIgnore, progress)


# Remote handling
class RemoteSyncDownCall(threading.Thread):
    def __init__(self, file_name, config, disregardIgnore=False):
        self.file_name = file_name
        self.config = config
        self.disregardIgnore = disregardIgnore
        threading.Thread.__init__(self)

    def run(self):
        target = self.file_name

        if (type(target) is str or type(target) is unicode) and self.config is None:
            return False

        clearMessages()

        if type(target) is str or type(target) is unicode:
            performSyncDown(target, self.config, self.disregardIgnore)
        else:
            total = len(target)
            progress = Progress(total)

            for file, config in target:
                progress.add([file])

                performSyncDown(file, config, self.disregardIgnore, progress)


# Sets up a config file in a directory
class NewFtpSyncCommand(sublime_plugin.TextCommand):
    def run(self, edit, dirs):
        if len(dirs) == 0:
            dirs = [os.path.dirname(self.view.file_name())]

        default = os.path.join(sublime.packages_path(), 'FTPSync', defaultConnectioConfigName)

        for dir in dirs:
            config = os.path.join(dir, configName)

            invalidateConfigCache(dir)

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
                    for file in files:
                        if file not in fileNames:
                            syncFiles.append([root + "\\" + file, getConfigFile(root + "\\" + file)])

        # sync
        thread = RemoteSyncCall(syncFiles, None)
        threads.append(thread)
        thread.start()


# Synchronize down selected file/directory
class FtpSyncDownTarget(sublime_plugin.TextCommand):
    def run(self, edit, paths):
        syncFiles = []
        fileNames = []

        # gather files
        for target in paths:
            # TODO - also check whether the file is not already in an added directory
            if target not in fileNames:
                syncFiles.append([target, getConfigFile(target)])

        # sync
        thread = RemoteSyncDownCall(syncFiles, None)
        threads.append(thread)
        thread.start()


class Progress:
    def __init__(self, total, current=0):
        self.total = total
        self.current = 0
        self.entries = None

    def expand(self, count):
        self.total += count

    def add(self, entries):
        if self.entries is None:
            self.entries = []

        for entry in entries:
            if entry not in self.entries:
                self.entries.append(entry)

    def getTotal(self):
        if self.entries is None:
            return self.total
        else:
            return len(self.entries)

    def progress(self, by=1):
        self.current += int(by)

        if self.current > self.getTotal():
            self.current = self.getTotal()

    def getPercent(self, division=10):
        percent = int(ceil(float(self.current) / float(self.getTotal()) * 100))
        percent = ceil(percent / division)

        return percent
