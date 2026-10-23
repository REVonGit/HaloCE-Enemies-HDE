"""unarchive.py <archive> <out dir>: any archive libarchive reads (rar 4/5, 7z, zip, tar), no unrar needed; skips paths that
would leave out dir."""
import ctypes, os, sys
la = ctypes.CDLL('libarchive.so.13')
la.archive_read_new.restype = ctypes.c_void_p
la.archive_entry_pathname.restype = ctypes.c_char_p
la.archive_entry_pathname.argtypes = [ctypes.c_void_p]
la.archive_entry_size.restype = ctypes.c_longlong
la.archive_entry_size.argtypes = [ctypes.c_void_p]
la.archive_entry_filetype.restype = ctypes.c_uint
la.archive_entry_filetype.argtypes = [ctypes.c_void_p]
la.archive_error_string.restype = ctypes.c_char_p
for f in ('archive_read_support_filter_all','archive_read_support_format_all'): getattr(la,f).argtypes=[ctypes.c_void_p]
la.archive_read_open_filename.argtypes=[ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
la.archive_read_next_header.argtypes=[ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
la.archive_read_data.argtypes=[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
la.archive_read_data.restype=ctypes.c_ssize_t
a = la.archive_read_new(); la.archive_read_support_filter_all(a); la.archive_read_support_format_all(a)
src, out = sys.argv[1], sys.argv[2]
assert la.archive_read_open_filename(a, src.encode(), 10240) == 0, la.archive_error_string(a)
e = ctypes.c_void_p()
while True:
    r = la.archive_read_next_header(a, ctypes.byref(e))
    if r == 1: break
    if r < 0: print('ERR', la.archive_error_string(a)); break
    name = la.archive_entry_pathname(e).decode('utf-8', 'replace').replace('\\', '/')
    if '..' in name.split('/') or name.startswith('/'): continue
    dst = os.path.join(out, name)
    if name.endswith('/') or la.archive_entry_filetype(e) == 0o040000:   # a directory (rar names them without the slash)
        os.makedirs(dst, exist_ok=True); continue
    os.makedirs(os.path.dirname(dst) or out, exist_ok=True)
    buf = ctypes.create_string_buffer(65536); data = bytearray()
    while True:
        n = la.archive_read_data(a, buf, 65536)
        if n <= 0: break
        data += buf.raw[:n]
    open(dst, 'wb').write(data); print(len(data), name)
