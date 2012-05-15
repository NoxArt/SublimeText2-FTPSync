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
import ftplib
import shutil
import os
import hashlib
import json
import threading
import re


# Init

# global config
settings = sublime.load_settings('ftpsync.sublime-settings')

isDebug = settings.get('debug')
isDebugVerbose = settings.get('debug_verbose')
project_defaults = settings.get('project_defaults')

# global ignore pattern
ignore = settings.get('ignore')

coreConfig = {
    'ignore': ignore,
    'connection_timeout': settings.get('connection_timeout')
}

re_ignore = re.compile(ignore)


configName = 'ftpsync.settings'

# connection cache pool
connections = {}
# threads pool
threads = []
# individual folder configs, file => config path
configs = {}
# messages scheduled to be dumped to status bar
messages = []


def statusMessage(text):
    sublime.status_message(text)


def dumpMessages():
    messages.reverse()
    for message in messages:
        statusMessage(message)
        messages.remove(message)


# Finds folder among those opened to which the file belongs
def getRoot(folders, current):
    for folder in folders:
        if current.find(folder) != -1:
            return folder


# Returns configuration file for a given file
def getConfigFile(view):
    file_name = view.file_name()

    # try cached
    try:
        if configs[file_name] and isDebug and isDebugVerbose:
            print "FTPSync > Loading config: cache hit (key: " + file_name + ")"

        return configs[file_name]
    except KeyError:
        try:
            folders = view.window().folders()

            if folders is None or len(folders) is 0:
                return None

            config = os.path.join(getRoot(folders, file_name), configName)
            if os.path.exists(config) is True:
                if isDebug:
                    print "FTPSync > Loaded config: " + config + " > for file: " + file_name

                configs[file_name] = config
                return config
            else:
                if isDebug:
                    print "FTPSync > Found no config > for file: " + file_name

                return None
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
        if isDebug:
            print "FTPSync > Failed parsing configuration file: " + file_name

        messages.append("FTPSync > Failed parsing configuration file " + file_name + " (commas problem?)")
        sublime.set_timeout(dumpMessages, 4)
        return None

    result = {}

    for name in config:
        result[name] = dict(project_defaults.items() + config[name].items())
        result[name]['file_name'] = file_name

    final = dict(coreConfig.items() + {"connections": result}.items())

    return final


# Returns connection, connects if needed
def getConnection(hash, config):
    try:
        if connections[hash] and isDebug and isDebugVerbose:
            print "FTPSync > Connection cache hit (key: " + hash + ")"

        return connections[hash]
    except KeyError:
        connections[hash] = []

        for name in config['connections']:
            properties = config['connections'][name]

            port = properties['port']

            if properties['tls'] is True:
                connection = ftplib.FTP_TLS()
            else:
                connection = ftplib.FTP()

            try:
                connection.connect(properties['host'], port, properties['timeout'])
            except:
                if isDebug:
                    print "FTPSync [" + name + "] > Connection failed"

                messages.append("FTPSync [" + name + "] > Connection failed")
                sublime.set_timeout(dumpMessages, 4)

                try:
                    connection.quit()
                except:
                    connection.close()

                return

            if isDebug:
                print "FTPSync [" + name + "] > Connected to: " + properties['host'] + ":" + str(port) + " (timeout: " + str(properties['timeout']) + ") (key: " + hash + ")"

            if properties['tls'] is True:
                connection.auth()

                if isDebug:
                    print "FTPSync [" + name + "] > Authentication processed"

            if properties['username'] is not None:
                connection.login(properties['username'], properties['password'])
                if isDebug:
                    pass_present = " (using password: NO)"
                    if len(properties['password']) > 0:
                        pass_present = " (using password: YES)"

                    print "FTPSync [" + name + "] > Logged in as: " + properties['username'] + pass_present

            elif isDebug:
                print "FTPSync [" + name + "] > Anonymous connection"

            try:
                connection.cwd(properties['path'])
                connection.name = name

                connections[hash].append(connection)
            except:
                if isDebug:
                    print "FTPSync [" + name + "] > Failed to set path (probably connection failed)"

        # schedule connection timeout
        def closeThisConnection():
            closeConnection(hash)

        sublime.set_timeout(closeThisConnection, config['connection_timeout'] * 1000)

        # return all connections
        return connections[hash]


# Close all connections for a given config file
def closeConnection(hash):
    try:
        for connection in connections[hash]:
            try:
                connection.quit()
            except:
                connections.close()
            finally:
                if isDebug:
                    print "FTPSync [" + connection.name + "] > closed"

                connections[hash].remove(connection)

        if len(connections[hash]) == 0:
            connections.pop(hash)

    except:
        return


# Return server path for the uploaded file relative to specified path
def getMappedPath(root, config, file_name):
    config = os.path.dirname(config)
    fragment = os.path.relpath(file_name, config)
    return os.path.join(root, fragment).replace('\\', '/')


# Uploads given file
def performSync(view, file_name, config_file):
    config = loadConfig(config_file)

    if len(ignore) > 0 and re_ignore.search(file_name) is not None:
        return

    connections = getConnection(getConfigHash(config_file), config)
    index = -1
    stored = []
    error = []

    for name in config['connections']:
        index += 1

        if config['connections'][name]['ignore'] is not None and re.search(config['connections'][name]['ignore'], file_name):
            break

        path = getMappedPath(config['connections'][name]['path'], config['connections'][name]['file_name'], file_name)

        command = "STOR " + path

        try:
            connections[index].storbinary(command, open(file_name))
            stored.append(name)

            if isDebug:
                print "FTPSync [" + name + "] > uploaded " + os.path.basename(file_name) + " ==> " + command

        except:
            error.append(name)

    if len(stored) > 0:
        messages.append("FTPSync [remotes: " + ",".join(stored) + "] > uploaded " + os.path.basename(file_name))

        sublime.set_timeout(dumpMessages, 4)


# File watching
class RemoteSync(sublime_plugin.EventListener):
    def on_post_save(self, view):
        thread = RemoteSyncCall(view, view.file_name(), getConfigFile(view))
        threads.append(thread)
        thread.start()

    def on_close(self, view):
        config_file = getConfigFile(view)

        if config_file is not None:
            hash = getConfigHash(config_file)
            closeConnection(hash)


# Remote handling
class RemoteSyncCall(threading.Thread):
    def __init__(self, view, file_name, config):
        self.view = view
        self.file_name = file_name
        self.config = config
        threading.Thread.__init__(self)

    def run(self):
        if self.config is None:
            return False

        performSync(self.view, self.file_name, self.config)


# Sets up a config file in a directory
class NewFtpSyncCommand(sublime_plugin.TextCommand):
    def run(self, edit, dirs):
        if len(dirs) == 0:
            dirs = [os.path.dirname(self.view.file_name())]

        default = os.path.join(sublime.packages_path(), 'FTPSync', 'ftpsync.default-settings')

        for dir in dirs:
            config = os.path.join(dir, configName)

            if os.path.exists(config) is True:
                self.view.window().open_file(config)
            else:
                shutil.copyfile(default, config)
                self.view.window().open_file(config)
