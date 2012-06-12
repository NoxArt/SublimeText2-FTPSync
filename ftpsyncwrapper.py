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

import ftplib
import os
import re
import time

# to extract data from FTP LIST http://stackoverflow.com/questions/2443007/ftp-list-format
ftpListParse = re.compile("^([d-])[rxw-]{9}\s+\d+\s+\d+\s+\d+\s+(\d+)\s+(\w{1,3}\s+\d+\s+(?:\d+:\d+|\d{2,4}))\s+(.*?)$", re.M | re.I | re.U | re.L)

# For FTP LIST entries with {last modified} timestamp earlier than 6 months, see http://stackoverflow.com/questions/2443007/ftp-list-format
currentYear = int(time.strftime("%Y", time.gmtime()))

# List of FTP errors of interest
ftpErrors = {
    'noFileOrDirectory': 553,
    'cwdNoFileOrDirectory': 550
}


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
    def getMappedPath(self, file_path):
        config = os.path.dirname(self.config['file_path'])
        fragment = os.path.relpath(file_path, config)
        return os.path.join(self.config['path'], fragment).replace('\\', '/')


# FTP(S) connection
#
# uses Python's ftplib
#
# because of FTP_TLS added in v2.7 FTPSync uses imported library from v2.7.1
# shipped with the plugin
class FTPSConnection(AbstractConnection):

    def __init__(self, config, name):
        self.config = config
        self.name = name

        if self.config['tls'] is True:
            self.connection = ftplib.FTP_TLS()
        else:
            self.connection = ftplib.FTP()

    def connect(self):
        return self.connection.connect(self.config['host'], int(self.config['port']), int(self.config['timeout']))

    def authenticate(self):
        if self.config['tls'] is True:
            self.connection.auth()
            return True

        return False

    def login(self):
        self.connection.login(self.config['username'], self.config['password'])


    def put(self, file_path):
        path = self.getMappedPath(file_path)

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
        path = self.getMappedPath(file_path)

        command = "RETR " + path

        try:
            with open(file_path, 'wb') as f:

                self.connection.retrbinary(command, lambda data: f.write(data))

                return self.name

        except Exception, e:
            if str(e)[:3] == str(ftpErrors['noFileOrDirectory']):
                self.__makePath(path)

                self.put(file_path)

                return self.name
            else:
                print e

    def cwd(self, path):
        self.connection.cwd(path)

    def parseTime(self, time_val):
        if time_val.find(':') is -1:
            struct = time.strptime(time_val + str(" 00:00"), "%b %d %Y %H:%M")
        else:
            struct = time.strptime(str(currentYear) + " " + time_val, "%Y %b %d %H:%M")

        return time.mktime(struct)


    def list(self, path):
        path = str(self.getMappedPath(path))
        contents = []
        result = []
        self.connection.dir(path, lambda data: contents.append(data))

        for content in contents:
            split = ftpListParse.search(content)

            if split is None:
                continue

            isDir = split.group(1) == 'd'
            filesize = split.group(2)
            lastModified = split.group(3)
            name = split.group(4)

            content = {
                'name': name,
                'filesize': int(filesize),
                'lastModified': self.parseTime(lastModified),
                'isDir': isDir
            }

            if name != "." and name != "..":
                result.append(content)

        return result

    def close(self, connections, hash):
        try:
            self.connection.quit()
        except:
            self.connection.close()

        try:
            connections[hash].remove(self)
        except ValueError:
            return

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
