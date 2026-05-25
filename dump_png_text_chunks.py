#!/usr/bin/env python
# dump_png_text_chunks.py — view all PNG tEXt/zTXt/iTXt chunks, with pretty JSON formatting

import struct
import zlib
import json
from pathlib import Path

def dump_png_text_chunks(path: Path, out_file=None, indent=3):
    """Dump all text chunks from a PNG, formatting JSON if detected."""
    with open(path, "rb") as f:
        sig = f.read(8)
        if sig != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Not a valid PNG file")

        chunks = []
        while True:
            len_bytes = f.read(4)
            if not len_bytes:
                break
            length = struct.unpack(">I", len_bytes)[0]
            ctype = f.read(4)
            data = f.read(length)
            f.read(4)  # skip CRC

            if ctype in [b"tEXt", b"zTXt", b"iTXt"]:
                key, _, val = data.partition(b"\x00")
                key = key.decode("latin-1", "ignore")
                if ctype == b"zTXt":
                    # zTXt stores compression flag + zlib payload
                    try:
                        val = zlib.decompress(val[1:])
                    except Exception:
                        pass
                elif ctype == b"iTXt" and b"\x00" in val:
                    # iTXt has language and translated fields before text
                    parts = val.split(b"\x00")
                    val = parts[-1]
                try:
                    txt = val.decode("utf-8", "ignore")
                except Exception:
                    txt = repr(val)
                chunks.append((ctype.decode(), key, txt))

        def format_chunk(ctype, key, txt):
            # Try to pretty-print JSON content
            try:
                parsed = json.loads(txt)
                txt = json.dumps(parsed, indent=indent)
            except Exception:
                pass
            return f"[{ctype}] {key}:\n{txt}\n" + "-" * 80 + "\n"

        if out_file:
            with open(out_file, "w", encoding="utf-8") as o:
                for ctype, key, txt in chunks:
                    o.write(format_chunk(ctype, key, txt))
            print(f"Wrote {len(chunks)} text chunks to {out_file}")
        else:
            for ctype, key, txt in chunks:
                print(format_chunk(ctype, key, txt))


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python dump_png_text_chunks.py <file|dir|glob> [out.txt]")
        sys.exit(1)

    target = sys.argv[1]
    out_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    paths = []

    p = Path(target)

    if "*" in target or "?" in target:
        # explicit glob
        paths = list(Path().glob(target))

    elif p.is_dir():
        # directory
        paths = list(p.glob("*.png"))

    elif p.exists():
        # single file
        paths = [p]

    else:
        print(f"No input found: {target}")
        sys.exit(1)

    if not paths:
        print("No PNG files found.")
        sys.exit(1)

    for png in paths:
        print(f"\n===== {png} =====\n")
        dump_png_text_chunks(png, out_file=None)



