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
