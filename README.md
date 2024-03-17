# msys2-downloader

This is a tool designed for downloading msys2 packages. It is particularly useful if you are cross-compiling on Linux for Windows.

### How to install

Option 1 (recommended): pipx creates a virtual environment for the installed application, ensuring that the application and its dependencies do not conflict with system Python packages.

```
pipx install git+https://github.com/nanoufo/msys2-downloader.git@main
```

Option 2:

```
pip install --user git+https://github.com/nanoufo/msys2-downloader.git@main
```

### How to use
```bash
$ msys2-download --extract-root /tmp/sysroot --env mingw64 curl
Downloaded https://mirror.yandex.ru/mirrors/msys2/mingw/mingw64/mingw64.db.tar.zst
Downloaded https://ftp.nluug.nl/pub/os/windows/msys2/builds/mingw/mingw64/mingw-w64-x86_64-brotli-1.1.0-1-any.pkg.tar.zst
Downloaded https://mirror.yandex.ru/mirrors/msys2/mingw/mingw64/mingw-w64-x86_64-nghttp2-1.60.0-1-any.pkg.tar.zst
...
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

### Useful
| Option | Description |
|---|---|
| --env ENV | Optional. Specifies the MSYS2 environment to search for packages. One of `clangarm64`, `clang32`, `clang64`, `mingw32`, `mingw64`, `ucrt64`. This option allows you to use short package names like `curl` instead of `mingw-w64-x86_64-curl`. |
| --extract-root PATH |  Optional. Specifies the directory where packages will be extracted. By default, packages are downloaded to the cache and not unpacked. |
| --no-deps | Download only the specified packages without their dependencies. |

### Less useful
| Option | Description |
|---|---|
| --base-url URL | Specifies the URL from which to download the package database and packages. The default is `https://mirror.msys2.org`. |
| --cache PATH | Specifies the directory where packages are downloaded. The default directory is `~/.cache/msys2-downloader`. |
