SublimeText2-FTPSync
====================

Simple and free plugin for FTP syncing.

*On 25th May 18:40UTC were published important bugfixes, restart SublimeText2 for PackageManager to update it automatically.*

Just added:
* Added possibility to disable automatic syncing and let you be in control
* Added command palette and context menu commands for uploading and downloading

Supports:
* Multiple named upload targets
* Ignored file regex patterns
* Secure transfer using TLS
* **NEW**  Manual multiple file & folder uploading (sidebar context menu)
* **NEW**  Manual multiple file & folder downloading (sidebar context menu)

Current focus:
* SFTP support

To mark a folder and descendants for upload insert *ftpsync.settings* file in following format. Don't worry - the skeleton can be simply inserted using *Preferences > Package Settings > FTPSync > Setup FTPSync in this folder* or using context menu in Side bar or using Control/CMD+Shift+P.

    {
    	<connection_name>: {
    		host: {string},

    		username: {null|string=null}, // null means anonymous manipulation
    		password: {null|string=""},

    		path: {string="/"}, // remote root for these files

            upload_on_save: true, // whether upload on save or manually

    		port: {int=21},
    		tls: {bool=false}, // use secured transfer
    		timeout: {int=30}, // seconds to invalidate the cached connection
    		ignore: {null|string}, // regular expression, matched against file path - not applied for downloading
    	} //,
        // <connection2_name>: { ... }
    }


Files are automatically uploaded on save (unless disabled by setting).

Released under MIT licence.

Feel free to add issues, ideas, pull requests...

**@NoxArt**








Tips
----

* **Upload different language versions to different servers of paths**

        {
        	<connection_name>: {
        		host: "ftp.host.en.com",
        		ignore: "/locale/(?!fr)\\w+/.*"
        	},
        	<connection2_name>: {
        		host: "ftp.host.cz.com",
        		ignore: "/locale/(?!cz)\\w+/.*"
        	}
        }