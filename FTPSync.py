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
settings = sublime.load_settings('ftpsync.sublime-settings')
project_defaults = settings.get('project_defaults')
ignore = settings.get('ignore')

re_ignore = re.compile(ignore)

isDebug = settings.get('debug')
configName = 'ftpsync.settings'
connections = {}
threads = []
configs = {}


# Aux
def statusMessage(text):
    sublime.status_message("FTPSync > " + text)


def getRoot(folders, current):
    for folder in folders:
        if current.find(folder) != -1:
            return folder


def getConfigFile(view):
    file_name = view.file_name()
    try:
        if isDebug:
            print "FTPSync > Loading config: cache hit (key: " + file_name + ")"

        return configs[file_name]
    except KeyError:
        folders = view.window().folders()

        config = os.path.join(getRoot(folders, file_name), configName)
        if os.path.exists(config) is True:
            if isDebug:
                print "FTPSync > Loaded config: " + config + " > for file: " + file_name

            configs[file_name] = config
            return config
        else:
            if isDebug:
                print fFTPSync > ile_name
                print "FTPSync > Found no config > for file: " + file_name

            return None


def getConfigHash(file_name):
    return hashlib.md5(file_name).hexdigest()


def loadConfig(file_name):
    config = json.load(open(file_name))
    result = {}

    for name in config:
        result[name] = dict(project_defaults.items() + config[name].items())
        result[name]['file_name'] = file_name

    return dict({"ignore": ignore}.items() + {"connections": result}.items())


def getConnection(hash, config):
    try:
        if isDebug:
            print "FTPSync > Connection cache hit (key: " + hash + ")"

        return connections[hash]
    except KeyError:
        connections[hash] = []

        for name in config['connections']:
            properties = config['connections'][name]

            port = 21
            if properties['port'] is "auto" and properties['tsl'] is True:
                port = 443

            # missing FTP_TLS in 2.6 ??!
            if properties['tsl'] is True:
                connection = ftplib.FTP()
            else:
                connection = ftplib.FTP()

            connection.connect(properties['host'], port, properties['timeout'])
            if isDebug:
                print "FTPSync [" + name + "] > Connected to: " + properties['host'] + ":" + str(port) + " (timeout: " + str(properties['timeout']) + ") (key: " + hash + ")"

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
                connection.cwd(properties['root'])

                connections[hash].append(connection)
            except:
                if isDebug:
                    print "FTPSync [" + name + "] > Failed to set path (probably connection failed)"

        return connections[hash]


def getMappedPath(root, config, file_name):
    config = os.path.dirname(config)
    fragment = os.path.relpath(file_name, config)
    return os.path.join(root, fragment)


# Syncing
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

        path = getMappedPath(config['connections'][name]['root'], config['connections'][name]['file_name'], file_name)

        command = "STOR " + path

        try:
            connections[index].storbinary(command, open(file_name))
            stored.append(name)
        except:
            error.append(name)

    #statusMessage("synchronized " + os.path.basename(file_name) + " with remotes: " + ", ".join(stored))


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
