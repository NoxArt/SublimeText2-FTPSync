SublimeText2-FTPSync
====================
*For Sublime Text 2 and Sublime Text 3*

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
* Remote browsing and manipulating via file list

**Now Sublime Text 3 compatible**, base commit by Dmitry Loktev!

WIP features:
* Passwords set via dialog, not stored in a file
* Considering: Events/hooks in FTPSync actions (preupload)

For more info look into [Wiki](https://github.com/NoxArt/SublimeText2-FTPSync/wiki/_pages)


How to use
----------

To mark a folder and descendants for upload insert **ftpsync.settings** file in following format. Don't worry - the skeleton can be simply inserted using *Preferences > Package Settings > FTPSync > Setup FTPSync in this folder* or using context menu in Side bar or using Control/CMD+Shift+P.

Simple settings file:
(*does not contain all options*)

     {
        <connection_name>: {
            host: {string}, // url of the ftp server
            username: {string=null},
            password: {string=""},

            path: {string="/"}, // your project's root path on the _server_

            upload_on_save: {bool=true}, // whether upload on save [true] or only manually [false]
            tls: {bool=false}, // recommended, server needs to support, but not enforce SSL_REUSE

            // ...
        }
    }


[All connection settings](https://github.com/NoxArt/SublimeText2-FTPSync/wiki/All-settings).

Files are automatically uploaded **on save** (unless disabled by _upload\_on\_save_=false setting). In your newly created settings file some options are preceded with `//`, this means they are commented out (and default value from global settings file is used) - remove the `//` to enable the entry.


Drawbacks and notes
---------------------

* FTPS is not supported at the moment and is not planned in near future (you can use [SFTP](http://wbond.net/sublime_packages/sftp) or [Mote](https://github.com/SublimeText/Mote) plugins)
* SSL/TLS is not supported for servers that enforce SSL_REUSE
* Does not support continuous watching and syncing, only (after) manual action
* Does not support proxy connections
* Does not support remote diff at the moment


About
-----

Done by **@NoxArt** ~ [Twitter](https://twitter.com/NoxArt)

Released under **MIT licence**.


<form action="https://www.paypal.com/cgi-bin/webscr" method="post" target="_top">
<input type="hidden" name="cmd" value="_s-xclick">
<input type="hidden" name="encrypted" value="-----BEGIN PKCS7-----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-----END PKCS7-----
">
<input type="image" src="https://www.paypalobjects.com/en_US/i/btn/btn_donate_LG.gif" border="0" name="submit" alt="PayPal - The safer, easier way to pay online!">
<img alt="" border="0" src="https://www.paypalobjects.com/en_US/i/scr/pixel.gif" width="1" height="1">
</form>
*If you're happy with FTPSync you can buy me a snack :)*


Feel free to add issues, ideas, pull requests...

Thanks to [castus](https://github.com/castus), [tommymarshall](https://github.com/tommymarshall), [TotallyInformation](https://github.com/TotallyInformation), [saiori](https://github.com/saiori), [vnabet](https://github.com/vnabet), [Jcrs](https://github.com/Jcrs), [ItayXD](https://github.com/ItayXD), [bibimij](https://github.com/bibimij), [digitalmaster](https://github.com/digitalmaster), [alfaex](https://github.com/alfaex), [seyDoggy](https://github.com/seyDoggy), Nuno, [mikedoug](https://github.com/mikedoug), [stevether](https://github.com/stevether), [zaus](https://github.com/zaus), [noAlvaro](https://github.com/noAlvaro), [zofie86](https://github.com/zofie86), [fma965](https://github.com/fma965), [PixelVibe](https://github.com/PixelVibe), [Kaisercraft](https://github.com/Kaisercraft), [benkaiser](https://github.com/benkaiser), [anupdebnath](https://github.com/anupdebnath), [sy4mil](https://github.com/sy4mil), [leek](https://github.com/leek), [surfac](https://github.com/surfac), [mitsurugi](https://github.com/mitsurugi), [MonoSnippets](https://github.com/MonoSnippets), [Zegnat](https://github.com/Zegnat), [cwhittl](https://github.com/cwhittl), [shadowsdweller](https://github.com/shadowsdweller), [adiulici01](https://github.com/adiulici01), [tablatronix](https://github.com/tablatronix), [bllim](https://github.com/bllim), [Imaulle](https://github.com/Imaulle), [friskfly](https://github.com/friskfly), [lysenkobv](https://github.com/lysenkobv), [nosfan1019](https://github.com/nosfan1019), [smoochieboochies](https://github.com/smoochieboochies), [Dmitry Loktev](https://github.com/unknownexception), [fedesilvaponte](https://github.com/fedesilvaponte), [fedegonzaleznavarro](https://github.com/fedegonzaleznavarro), [camilstaps](https://github.com/camilstaps), [maknapp](https://github.com/maknapp), [certainlyakey](https://github.com/certainlyakey), [victorhqc](https://github.com/victorhqc), [eniocarv](https://github.com/eniocarv), [molokoloco](https://github.com/molokoloco), [tq0fqeu](https://github.com/tq0fqeu), [Arachnoid](https://github.com/Arachnoid) for reporting issues, ideas and fixing!



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
