SublimeText2-FTPSync
====================

Simple and free plugin for FTP syncing. Just hit the _save_ as usual and it's upped.

What's there for you?
* Multiple named upload targets
* Ignored file regex patterns
* Secure transfer using TLS
* Downloading via temporary file (better stability)
* Determining newer remote files, overwrite protection
* Manual multiple file & folder up/downloading (sidebar context menu)
* Multithreaded uploading and downloading
* Local&remote renaming and deleting
* Progress bar for multiple up/download
* [ *experimental* ] Remote browsing and manipulating via file list


For more info look into [Wiki](https://github.com/NoxArt/SublimeText2-FTPSync/wiki/_pages)


How to use
----------

To mark a folder and descendants for upload insert *ftpsync.settings* file in following format. Don't worry - the skeleton can be simply inserted using *Preferences > Package Settings > FTPSync > Setup FTPSync in this folder* or using context menu in Side bar or using Control/CMD+Shift+P.

Simply:

     {
        <connection_name>: {
            host: {string}, // url of the ftp server

            username: {string=null},
            password: {string=""},

            path: {string="/"}, // your project's root path on the _server_

            upload_on_save: {bool=true}, // whether upload on save [true] or manually [false]

            tls: {bool=false}, // set [true] to use secured transfer, recommended!
            // (server needs to support, but not enforce SSL_REUSE)
        }
    }


Whole connection config:

    {
        <connection_name>: {
            host: {string},

            username: {null|string=null}, // null means anonymous manipulation
            password: {null|string=""},

            path: {string="/"}, // your project's root path on the _server_

            upload_on_save: {bool=true}, // whether upload on save or manually
            download_on_open: {bool=false}, // checks whether there's a newer remote file on opening a file
            overwrite_newer_prevention: {bool=true}, // overwrite protection when remote file is newer
            upload_delay: {int=0}, // delays [seconds] upload triggered by upload_on_save

            encoding: {string=auto}, // encoding used for filenames on FTP server; auto = UTF8 if extension enabled, otherwise nothing
            port: {int=21}, // remote port, pretty much always 21, unless SFTP
            tls: {bool=false}, // set true to use secured transfer, recommended! (server needs to support)
            passive: {bool=true}, // whether to use passive or active connection
            timeout: {int=30}, // [seconds] to invalidate the cached connection
            ignore: {null|string}, // regular expression, matched against file path - not applied for downloading
            time_offset: {int=0}, // [seconds] to adjust for a different timezone of server
            set_remote_lastmodified: {bool=true}, // if MFMT extension is availible, will set true lastModified based on local file

            default_folder_permissions: {string=755}, // default permissions for newly created folders
            default_local_permissions: {null|string="auto"}, // permissions for downloaded files, "auto" = same as on server
            always_sync_local_permissions: {bool=true}, // set permissions for downloaded file even if it already exists

            after_save_watch: {null|list<list<subfolder, filepatter>>=null} // after save watch
            // example: [ [ "code/assets/css", "*.css" ], [ "code/assets/", "*.jpg, *.png, *.gif" ] ]
            // more in Wiki

        } //,
        // <connection2_name>: { ... }
    }

Files are automatically uploaded **on save** (unless disabled by _upload\_on\_save_=false setting). In your newly created settings file some options are preceded with `//`, this means they are commented out (and default value from global settings file is used) - remove the `//` to enable the entry.


Drawbacks and notes
---------------------

* FTPS is not supported at the moment and is not planned in near future (you can use [SFTP](http://wbond.net/sublime_packages/sftp) or [Mote](https://github.com/SublimeText/Mote) plugins)
* SSL/TLS is not supported for servers that enforce SSL_REUSE
* Does not support continuous watching and syncing, only (after) manual action
* Does not support proxy connections at the moment
* Does not support remote diff at the moment


About
-----

Done by **@NoxArt** ~ [Twitter](https://twitter.com/#!/NoxArt)

Released under MIT licence.

Feel free to add issues, ideas, pull requests...

Thanks to [castus](https://github.com/castus), [tommymarshall](https://github.com/tommymarshall), [TotallyInformation](https://github.com/TotallyInformation), [saiori](https://github.com/saiori), [vnabet](https://github.com/vnabet), [Jcrs](https://github.com/Jcrs), [ItayXD](https://github.com/ItayXD), [bibimij](https://github.com/bibimij), [digitalmaster](https://github.com/digitalmaster), [alfaex](https://github.com/alfaex), [seyDoggy](https://github.com/seyDoggy), Nuno, [mikedoug](https://github.com/mikedoug), [stevether](https://github.com/stevether), [zaus](https://github.com/zaus), [noAlvaro](https://github.com/noAlvaro), [zofie86](https://github.com/zofie86), [fma965](https://github.com/fma965), [PixelVibe](https://github.com/PixelVibe), [Kaisercraft](https://github.com/Kaisercraft), [benkaiser](https://github.com/benkaiser), [anupdebnath](https://github.com/anupdebnath), [sy4mil](https://github.com/sy4mil), [leek](https://github.com/leek), [surfac](https://github.com/surfac), [mitsurugi](https://github.com/mitsurugi), [MonoSnippets](https://github.com/MonoSnippets), [Zegnat](https://github.com/Zegnat), [cwhittl](https://github.com/cwhittl), [shadowsdweller](https://github.com/shadowsdweller), [adiulici01](https://github.com/adiulici01), [tablatronix](https://github.com/tablatronix), [bllim](https://github.com/bllim), [Imaulle](https://github.com/Imaulle) and [friskfly](https://github.com/friskfly), [lysenkobv](https://github.com/lysenkobv), [nosfan1019](https://github.com/nosfan1019), [smoochieboochies](https://github.com/smoochieboochies) for reporting issues, ideas and fixing!


Tips
----

* **Set key bindings (hotkeys) for frequent actions you use**

Please edit only `Key Bindings - User` (clicking `Preferences > Package Control > FTPSync > Key Bindings - User` will open that file for you). You can use the contents of `Key Bindings - Default` as a template and copy it there. If you edit `Key Bindings - Default` (either Sublime's or FTPSync's), your changes will be lost on update.

* **Renaming and deleting**

Please keep in mind that for deleting and renaming on server you need to use `FTPSync > Rename` and `FTPSync > Delete` features, not those in Sublime Text 2 or SideBarEnhancements.

* **Working from more places? Or in team?**

You can either use *download_on_open=true* to check files upon openning or *FTPSync: Check current file* command to see whether you have the same version as is on all servers. Using *overwrite_newer_prevention* is also recommended (it's actually enabled by default).

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

* **Using file compilation? Want to upload as well?**

You can use *after_save_watch* option to setup files to be watched for change after uploading on save. [Learn how to use in Wiki](https://github.com/NoxArt/SublimeText2-FTPSync/wiki/Why-and-how-to-use-afterwatch).





#### *Recent -though older- changes*

* Setting true lastModified (based on local file's last modified value) on FTP server, if it has MFMT extension installed
* Mutlithreaded upload and download for much better speed
* Added empty shortcuts [wiki entry](https://github.com/NoxArt/SublimeText2-FTPSync/wiki/Key-bindings)
* Fixed Renaming feature
* Added Delete feature (confirm dialogue inspired by [SideBarEnhancements](https://github.com/titoBouzout/SideBarEnhancements))
* Improved dialogues
* Remembering "overwrite cancelled" decision
* Fixing special characters in file path
* Stability improvement (fresh connection per non-multithreaded command: those use their own connection handling)
* Experimental browsing feature
