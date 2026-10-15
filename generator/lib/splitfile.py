"""MCC's big data files (textures.dat, sounds_en.dat, sounds_neutral.dat, SPV3's bitmaps.map), whole or split.

Each can be the file itself or its numbered pieces next to where it would be (textures.dat.001, .002 ... as a
file-splitting tool writes them: every piece the same size but the last). A reader seeks and reads across the pieces as
if they were one file, so the pieces never need joining (they are big), and only the pieces a job reads need to be
there: a missing one raises MissingPart, which names it and the bytes it holds.

    import splitfile
    if splitfile.exists(path):
        with splitfile.open(path) as f: f.seek(off); data = f.read(n)
"""
import builtins, os


class MissingPart(FileNotFoundError):
    """a read needs a numbered piece that isn't there; the message names it and the byte range it holds"""
    pass


def parts(path):
    """the numbered pieces of path that exist, in order ([] if none)"""
    out, i = [], 1
    while os.path.exists(f'{path}.{i:03d}'):
        out.append(f'{path}.{i:03d}'); i += 1
    return out


def exists(path):
    """the file, or any of its pieces (a later piece alone counts: the earlier ones may just not be needed)"""
    if os.path.exists(path): return True
    d, b = os.path.split(path)
    return os.path.isdir(d or '.') and any(f.startswith(b + '.') and f[len(b) + 1:].isdigit() for f in os.listdir(d or '.'))


class SplitReader:
    """A file-like reader over path's numbered pieces: seek / tell / read / close, pieces opened as they are needed.
    size is the piece size (the largest piece present, or HCE_SPLIT_SIZE / 100 MiB when only a short one is)."""
    def __init__(s, path):
        """find path's pieces (FileNotFoundError when there are none) and work out the piece size"""
        s.path = path; s.pos = 0; s.fh = {}
        d, b = os.path.split(path)
        nums = sorted(int(f[len(b) + 1:]) for f in os.listdir(d or '.') if f.startswith(b + '.') and f[len(b) + 1:].isdigit())
        if not nums: raise FileNotFoundError(path)
        s.have = set(nums)
        # every piece but the last is the same size: the largest one present (the 100 MiB a splitter usually writes, when
        # only a short last piece is here)
        s.size = max(os.path.getsize(f'{path}.{k:03d}') for k in nums)
        if len(nums) == 1 and s.size < 104857600: s.size = int(os.environ.get('HCE_SPLIT_SIZE', 104857600))

    def _piece(s, k):
        """the open file of piece k (0-based; piece files are numbered from .001), raising MissingPart if absent"""
        if k not in s.fh:
            n = k + 1
            if n not in s.have:
                raise MissingPart(f'{s.path}.{n:03d} is needed (bytes {k * s.size:,}-{(k + 1) * s.size - 1:,}; '
                                  f'{(k * s.size) / 2**20:.0f}-{((k + 1) * s.size) / 2**20:.0f} MB)')
            s.fh[k] = builtins.open(f'{s.path}.{n:03d}', 'rb')
        return s.fh[k]

    def seek(s, off, whence=0):
        """move the position: absolute (whence 0) or relative to the current position (anything else)"""
        s.pos = off if whence == 0 else s.pos + off
        return s.pos

    def tell(s): return s.pos

    def read(s, n=-1):
        """read n bytes (all that remain for -1) across piece boundaries, advancing the position"""
        out = b''
        while n != 0:
            k, o = divmod(s.pos, s.size)
            f = s._piece(k); f.seek(o)
            b = f.read(s.size - o if n < 0 else min(n, s.size - o))
            if not b: break
            out += b; s.pos += len(b)
            if n > 0: n -= len(b)
        return out

    def close(s):
        """close every piece opened so far"""
        for f in s.fh.values(): f.close()
        s.fh = {}

    def __enter__(s): return s
    def __exit__(s, *a): s.close()


def open(path):
    """path as one readable file: the file itself, else its pieces"""
    return builtins.open(path, 'rb') if os.path.exists(path) else SplitReader(path)
