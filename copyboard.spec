# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/*', 'assets')],
    hiddenimports=['PIL', 'PIL.Image', 'PIL.ImageGrab', 'PIL.ImageDraw',
                   'pystray', 'pystray._win32', 'pystray._util',
                   'json', 'hashlib', 'sqlite3', 'ctypes', 'shutil'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'email', 'http', 'html', 'xml', 'xmlrpc',
        'unittest', 'test', 'pydoc', 'doctest', 'bz2', 'lzma',
        'multiprocessing', 'concurrent', 'asyncio',
        'distutils', 'setuptools', 'pkg_resources',
        'urllib', 'ftplib', 'imaplib', 'nntplib', 'poplib', 'smtplib',
        'socketserver', 'wsgiref', 'cgi', 'cgitb',
        'ensurepip', 'venv', 'zipapp',
        'lib2to3', 'idlelib', 'turtledemo',
        'tkinter.colorchooser', 'tkinter.filedialog',
        'tkinter.simpledialog', 'tkinter.scrolledtext', 'tkinter.dnd',
        'difflib', 'netrc', 'tarfile',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Copyboard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\icon.png',
)
