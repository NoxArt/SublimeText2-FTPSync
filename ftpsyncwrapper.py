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

import ftplib
import os

ftpErrors = {
    'noFileOrDirectory': 553,
    'cwdNoFileOrDirectory': 550
}


class ConnectionWrapper:

    def __init__(self, config, name, isDebug):
        self.config = config
        self.isDebug = isDebug

        if self.isConnectionSSH():
            return
        else:
            if self.config['tls'] is True:
                self.connection = ftplib.FTP_TLS()
            else:
                self.connection = ftplib.FTP()

        self.connection.name = name

    def isConnectionSSH(self):
        return 'ssh' in self.config or ('private_key' in self.config and self.config['private_key'] is not None)

    def connect(self):
        if self.isConnectionSSH():
            return True
        else:
            return self.connection.connect(self.config['host'], self.config['port'], self.config['timeout'])

    def authenticate(self):
        if self.isConnectionSSH():
            return True
        elif self.config['tls'] is True:
            self.connection.auth()

            if self.isDebug:
                print "FTPSync [" + self.connection.name + "] > Authentication processed"

        return False

    def login(self):
        if self.isConnectionSSH():
            return True
        else:
            self.connection.login(self.config['username'], self.config['password'])

    # Return server path for the uploaded file relative to specified path
    def getMappedPath(self, file_name):
        config = os.path.dirname(self.config['file_name'])
        fragment = os.path.relpath(file_name, config)
        return os.path.join(self.config['path'], fragment).replace('\\', '/')

    def makePath(self, path):
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

    def put(self, file_path):
        path = self.getMappedPath(file_path)

        if self.isConnectionSSH():
            return
        else:
            command = "STOR " + path

            try:
                self.connection.storbinary(command, open(file_path))

                if self.isDebug:
                    print "FTPSync [" + self.connection.name + "] > uploaded " + os.path.basename(file_path) + " ==> " + command

                return self.connection.name

            except Exception, e:
                if str(e)[:3] == str(ftpErrors['noFileOrDirectory']):
                    self.makePath(path)

                    self.connectionPut(file_path)

    def cwd(self, path):
        if self.isConnectionSSH():
            return
        else:
            self.connection.cwd(path)

    def close(self, connections, hash):
        if self.isConnectionSSH():
            return
        else:
            try:
                self.connection.quit()
            except:
                self.connection.close()

        if self.isDebug and hasattr(self.connection, 'name'):
            print "FTPSync [" + self.connection.name + "] > closed"

        try:
            connections[hash].remove(self.connection)
        except ValueError:
            return
