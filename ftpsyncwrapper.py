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
import ftplib
import os
import re
import time

# FTPSync libraries
from ftpsyncfiles import Metafile


# ==== Initialization and optimization =====================================================

# to extract data from FTP LIST http://stackoverflow.com/questions/2443007/ftp-list-format
ftpListParse = re.compile("^([d-])[rxws-]{9}\s+\d+\s+[\w\d]+\s+[\w\d]+\s+(\d+)\s+(\w{1,3}\s+\d+\s+(?:\d+:\d+|\d{2,4}))\s+(.*?)$", re.M | re.I | re.U | re.L)

# For FTP LIST entries with {last modified} timestamp earlier than 6 months, see http://stackoverflow.com/questions/2443007/ftp-list-format
currentYear = int(time.strftime("%Y", time.gmtime()))

# List of FTP errors of interest
ftpErrors = {
    'noFileOrDirectory': 553,
    'cwdNoFileOrDirectory': 550,
    'rnfrExists': 350
}



# ==== Exceptions ==========================================================================

class ConnectionClosedException(Exception):
    pass


# ==== Content =============================================================================

# Factory function - returns and instance of a proper class based on the configuration
# currently differs between FTP(S) and SFTP
#
# SFTP currently not implemented
#
# @type config: dict
# @type name: string
# @param name: user-defined name of a connection
#
# @return AbstractConnection
def CreateConnection(config, name):
    if 'private_key' in config and config['private_key'] is not None:
        raise NotImplementedError
    else:
        return FTPSConnection(config, name)


# Base class for all connection classes
class AbstractConnection:

    # Return server path for the uploaded file relative to specified path
    #
    # @example:
    #   file_path: /user/home/NoxArt/web/index.php
    #   config['path']: /www/
    #   config['file_path']: /user/home/NoxArt/
    #
    #   result: /www/web/index.php
    #
    # @type self: AbstractConnection
    # @type file_path: string
    #
    # @return string remote file path
    def _getMappedPath(self, file_path):
        config = os.path.dirname(self.config['file_path'])
        fragment = os.path.relpath(file_path, config)
        return self._postprocessPath(os.path.join(self.config['path'], fragment))

    # Tweaks a remote path before using it
    #
    # @type self: AbstractConnection
    # @type file_path: string
    #
    # @return string remote file path
    def _postprocessPath(self, path):
        return path.replace('\\', '/')


# FTP(S) connection
#
# uses Python's ftplib
#
# because of FTP_TLS added in v2.7 FTPSync uses imported library from v2.7.1
# shipped with the plugin
class FTPSConnection(AbstractConnection):

    # Constructor
    #
    # @type self: FTPSConnection
    # @type config: dict
    # @param config: only the connection part of config
    # @type name: string
    # @param name: connection name from config
    def __init__(self, config, name):
        self.config = config
        self.name = name
        self.isClosed = False

        if self.config['tls'] is True:
            self.connection = ftplib.FTP_TLS()
        else:
            self.connection = ftplib.FTP()


    # Destructor, closes connection
    #
    # @type self: FTPSConnection
    def __del__(self):
        self.close()


    # Connects to remote server
    #
    # @type self: FTPSConnection
    def connect(self):
        self.connection.connect(self.config['host'], self.config['port'], self.config['timeout'])
        self.connection.set_pasv(self.config['passive'])


    # Authenticates if necessary
    #
    # @type self: FTPSConnection
    #
    # @return bool whether the authentication happened or not
    def authenticate(self):
        if self.config['tls'] is True:
            self.connection.auth()
            return True

        return False


    # Logs into the remote server
    #
    # @type self: FTPSConnection
    def login(self):
        self.connection.login(self.config['username'], self.config['password'])


    # Send an empty/keep-alive message to server
    #
    # @type self: FTPSConnection
    def keepAlive(self):
        self.connection.voidcmd("NOOP")


    # Uploads a file to remote server
    #
    # @type self: FTPSConnection
    # @type file_path: string
    #
    # @return string|None name of this connection or None
    #
    # @global ftpErrors
    def put(self, file_path, new_name = None):
        remote_file = file_path
        if new_name is not None:
            remote_file = self._postprocessPath(os.path.join(os.path.split(file_path)[0], new_name))

        path = self._getMappedPath(remote_file)

        command = "STOR " + path

        try:
            uploaded = open(file_path, "rb")

            self.connection.storbinary(command, uploaded)

            uploaded.close()

            return self.name

        except Exception, e:
            if str(e)[:3] == str(ftpErrors['noFileOrDirectory']):
                self.__makePath(path)

                self.put(file_path)

                return self.name
            else:
                print e


    def get(self, file_path):
        path = self._getMappedPath(file_path)

        command = "RETR " + path

        try:
            with open(file_path, 'wb') as f:

                self.connection.retrbinary(command, lambda data: f.write(data))

                self.close()

                return self.name

        except Exception, e:
            print e


    def rename(self, file_path, new_name):
        path = self._getMappedPath(os.path.dirname(file_path))
        base = os.path.basename(file_path)

        try:
            self.cwd(path)
        except Exception, e:
            if str(e)[:3] == str(ftpErrors['noFileOrDirectory']):
                self.__makePath(path)

        try:
            self.connection.voidcmd("RNFR " + base)
        except Exception, e:
            if str(e)[:3] == str(ftpErrors['cwdNoFileOrDirectory']):
                self.put(file_path, new_name)
                return base

        try:
            self.connection.voidcmd("RNFR " + base)
        except:
            if str(e)[:3] == str(ftpErrors['rnfrExists']) and str(e).find('Aborting previous'):
                self.connection.voidcmd("RNTO " + new_name)
                return base

        self.connection.voidcmd("RNTO " + new_name)

        return base


    def cwd(self, path):
        self.connection.cwd(path)


    def list(self, path):
        path = self._getMappedPath(path)
        contents = []
        result = []
        self.connection.dir(path, lambda data: contents.append(data))

        for content in contents:
            if self.config['debug_extras']['print_list_result'] is True:
                print "FTPSync <debug> LIST line: " + str(content)

            split = ftpListParse.search(content)

            if split is None:
                continue

            isDir = split.group(1) == 'd'
            filesize = split.group(2)
            lastModified = split.group(3)
            name = split.group(4)

            data = Metafile(name, isDir, self.__parseTime(lastModified), filesize)

            if name != "." and name != "..":
                result.append(data)

        return result


    def close(self, connections=[], hash=None):
        try:
            self.connection.quit()
        except:
            self.connection.close()
        finally:
            self.isClosed = True

        if len(connections) > 0 and hash is not None:
            try:
                connections[hash].remove(self)
            except ValueError:
                return


    def __checkClosed(self):
        if self.isClosed is True:
            raise ConnectionClosedException


    def __parseTime(self, time_val):
        if time_val.find(':') is -1:
            struct = time.strptime(time_val + str(" 00:00"), "%b %d %Y %H:%M")
        else:
            struct = time.strptime(str(currentYear) + " " + time_val, "%Y %b %d %H:%M")

        return time.mktime(struct)


    def __makePath(self, path):
        self.connection.cwd(self.config['path'])

        relative = os.path.relpath(path, self.config['path'])

        folders = relative.split("\\")
        if type(folders) is str:
            folders = relative.split("/")

        index = 0
        for folder in folders:
            index += 1

            try:
                if index < len(folders):
                    self.connection.cwd(folder)
            except Exception, e:
                if str(e)[:3] == str(ftpErrors['cwdNoFileOrDirectory']):
                    self.connection.mkd(folder)
                    self.connection.cwd(folder)


#class SSHConnection():
