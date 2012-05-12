SublimeText2-FTPSync
====================

Simple and free plugin for FTP syncing.

Supports:
* Multiple named upload targets
* Ignored file regex patterns
* Secured transfer using TLS

To mark a folder and descendants for upload, insert *ftpsync.settings* file in format:

    {
    	<connection_name>: {
    		host: {string},

    		username: {null|string=null},
    		password: {null|string=""},

    		path: {string="/"},

    		port: {int=21},
    		tls: {bool=false},
    		timeout: {int=30},
    		ignore: {null|string},
    		constrains: {list=[]} // not implemented yet
    	}
    }

You can create such file using *Preferences > Package Settings > FTPSync > Setup FTPSync in this folder*.

Files are automatically uploaded on save.

Released under MIT licence.

Feel free to add issues, ideas, pull requests...

**@NoxArt**