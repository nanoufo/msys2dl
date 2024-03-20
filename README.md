# msys2-downloader

This tool is designed for downloading, extracting MSYS2 packages and converting them to Debian packages for use in cross-compiling. While you won't be able to run executable files, you'll have access to includes and libraries to link against. 

## How to install

Option 1 (recommended): pipx creates a virtual environment for the installed application, ensuring that the application and its dependencies do not conflict with system Python packages.

```
pipx install git+https://github.com/nanoufo/msys2-downloader.git@main
```

Option 2:

```
pip install --user git+https://github.com/nanoufo/msys2-downloader.git@main
```

## How to use

Conversion to Debian packages.

Note: Use this feature only with `mingw64` or `mingw32` environments. Files in packages from these environments are relocated from `/mingw{32,64}` to `/usr/{i686,x86_64}-w64-mingw32`, where distribution-provided tools expect them to be.

Note: Dependencies are downloaded by default. Use the `--no-deps` flag to opt-out..
 
```bash
$ msys2-download --make-deb --output /tmp/deb --env mingw64 wxwidgets3.2-msw
Downloading packages...
mingw-w64-x86_64-mpdecimal-4.0.0-1 downloaded
mingw-w64-x86_64-libpng-1.6.43-1 downloaded
...
mingw-w64-x86_64-wxwidgets3.2-msw-3.2.4-1 downloaded
...
Done!
Building deb packages...
Done!
$ ls /tmp/deb
 bzip2-msys2-mingw64_1.0.8-3_all.deb
 expat-msys2-mingw64_2.6.2-1_all.deb
 gcc-libs-msys2-mingw64_13.2.0-5_all.deb
...
 wxwidgets3.2-msw-msys2-mingw64_3.2.4-1_all.deb
...
$ sudo dpkg -i /tmp/deb/*
...
Setting up wxwidgets3.2-msw-msys2-mingw64 (3.2.4-1) ...
...
$ ls -1 /usr/x86_64-w64-mingw32/lib/
...
libwx_mswu_gl-3.2.a
libwx_mswu_gl-3.2.dll.a
...
```

Extracting.

Note: Dependencies are downloaded by default. Use the `--no-deps` flag to opt-out.
```bash
$ msys2-download --extract --output /tmp/sysroot --env mingw64 curl
Downloading packages...
mingw-w64-x86_64-openssl-3.2.1-1 downloaded
mingw-w64-x86_64-libtasn1-4.19.0-1 downloaded
...
mingw-w64-x86_64-curl-8.6.0-1 downloaded
Done!
Extracting packages...
Done!
$ tree -L 2 /tmp/sysroot
/tmp/sysroot
└── mingw64
    ├── bin
    ├── etc
    ├── include
    ├── lib
    ├── libexec
    └── share
```

## Options

### Basic
| Option                          | Description                                                                                                                                                                                                                                    |
|---------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `--env ENV`                     | Optional. Specifies the MSYS2 environment to search for packages. Choose from `clangarm64`, `clang32`, `clang64`, `mingw32`, `mingw64`, `ucrt64`. This option enables the use of short package names like `curl` instead of `mingw-w64-x86_64-curl`. |
| `--extract`                     | **Extraction mode.** Unpack the contents of packages to the output directory.                                                                                                                                                                     |
| `--make-deb`                    | **Build .deb mode.** Convert MSYS2 packages to Debian packages. For `mingw32` and `mingw64`, files are relocated from `/mingw{32,64}` to `/usr/{i686,x86_64}-w64-mingw32`.                                                                            |
| `--no-deps`                     | Download only the specified packages without their dependencies.                                                                                                                                                                               |
| `--output PATH`                 | Optional. Debian packages generated or extracted files will be located in this directory. By default, the current directory will be used.                                                                                                          |
| `--exclude PACKAGE [PACKAGE ...]`| Optional. Ignores these packages. When resolving dependencies, excluded packages' dependencies are excluded as well. Useful if you want to bypass libraries installed from other sources.                                                |

To combine `--exclude` with the list of included packages, use the following syntax:
```bash
$ msys2-download --exclude zlib -- curl 
```

### Advanced
| Option                           | Description                                                                                                  |
|----------------------------------|--------------------------------------------------------------------------------------------------------------|
| `--base-url URL`                  | Specifies the URL to download packages from. The default is `https://mirror.msys2.org`.                      |
| `--cache-dir PATH`                | Specifies the directory where packages are downloaded. The default directory is `~/.cache/msys2-downloader`. |
