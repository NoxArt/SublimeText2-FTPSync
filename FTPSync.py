import sublime
import sublime_plugin
import ftplib
import shutil
import os
import hashlib
import json
import threading


# Init
settings = sublime.load_settings('ftpsync.sublime-settings')
project_defaults = settings.get('project_defaults')
isDebug = settings.get('debug')
configName = 'ftpsync.settings'
connections = {}
threads = []
configs = {}


# Aux
def getRoot(folders, current):
    for folder in folders:
        if current.find(folder) != -1:
            return folder


def getConfigFile(view):
    file_name = view.file_name()
    try:
        if isDebug:
            print "Loading config: cache hit (key: " + file_name + ")"

        return configs[file_name]
    except KeyError:
        folders = view.window().folders()

        config = os.path.join(getRoot(folders, file_name), configName)
        if os.path.exists(config) is True:
            if isDebug:
                print "Loaded config: " + config + " > for file: " + file_name

            configs[file_name] = config
            return config
        else:
            if isDebug:
                print file_name
                print "Found no config > for file: " + file_name

            return None


def getConfigHash(file_name):
    return hashlib.md5(file_name).hexdigest()


def loadConfig(file_name):
    config = json.load(open(file_name))
    config['file_name'] = file_name

    return dict(project_defaults.items() + config.items())


def getConnection(hash, config):
    try:
        if isDebug:
            print "Connection cache hit (key: " + hash + ")"

        return connections[hash]
    except KeyError:
        port = 21
        if config['port'] is "auto" and config['tsl'] is True:
            port = 443

        if config['tsl'] is True:
            connection = ftplib.FTP()
        else:
            connection = ftplib.FTP()

        connection.connect(config['host'], port, config['timeout'])
        if isDebug:
            print "Connected to: " + config['host'] + ":" + str(port) + " (timeout: " + str(config['timeout']) + ") (key: " + hash + ")"

        if config['username'] is not None:
            connection.login(config['username'], config['password'])
            if isDebug:
                pass_present = " (using password: NO)"
                if len(config['password']) > 0:
                    pass_present = " (using password: YES)"

                print "Logged in as: " + config['username'] + pass_present

        elif isDebug:
            print "Anonymous connection"

        connection.cwd(config['root'])

        connections[hash] = connection

        return connection


def getMappedPath(root, config, file_name):
    config = os.path.dirname(config)
    fragment = os.path.relpath(file_name, config)
    return os.path.join(root, fragment)


# Syncing
def performSync(view, file_name, config_file):
    config = loadConfig(config_file)
    connection = getConnection(getConfigHash(config_file), config)
    path = getMappedPath(config['root'], config['file_name'], file_name)

    command = "STOR " + path

    connection.storbinary(command, open(file_name))


# File watching
class RemoteSync(sublime_plugin.EventListener):
    def on_post_save(self, view):
        thread = RemoteSyncCall(view, view.file_name(), getConfigFile(view))
        threads.append(thread)
        thread.start()


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
    def run(self, edit):
        default = os.path.join(sublime.packages_path(), 'FTPSync', 'ftpsync.default-settings')
        config = os.path.join(os.path.dirname(self.view.file_name()), configName)

        if os.path.exists(config) is True:
            self.view.window().open_file(config)
        else:
            shutil.copyfile(default, config)
            self.view.window().open_file(config)
