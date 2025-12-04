# WickedTracker

This automated script downloads latest Wicked Engine build and sends notification of new sucessful build artifact via Telegram. 
Then it loads the source code from the push that this build is based on.

By default all build files go to the "build" folder inside of the script and source code goes inside of the "code" folder. This behaviour can be overriden in the **config/config.yaml** file.
You can also setup bot with all API keys to send notifications via Telegram as soon as the build is download and code is copied.

You can also change what archives to download and unpack. By default it downloads the Content folder and binaries of the Windows Editor. If you're working from Linux, or don't want to download Content folder  you can just change the file name in the config.

Additionaly, you can set specifically which files to extract from the downloaded archive and whether the script should keep downloaded archives in the "downloads" folder or delete both the folder and the arhive as soon as it finishes the unpacking process.

On windows you can launch the script via the .bat file. On Linux (or if you hate .bat files for some reason) you can just type *python ./app/__main__.py* in the terminal.
