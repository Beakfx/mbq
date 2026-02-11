import struct, json, zlib, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

def pretty_print_png_json(file_path):
    """Read PNG metadata chunks (prompt/workflow) and print pretty JSON."""
    try:
        with open(file_path, "rb") as f:
            if f.read(8) != b"\x89PNG\r\n\x1a\n":
                print(f"[!] {file_path} is not a valid PNG")
                return

            while True:
                length_bytes = f.read(4)
                if not length_bytes:
                    break

                length = struct.unpack(">I", length_bytes)[0]
                ctype = f.read(4).decode("ascii", errors="ignore")
                data = f.read(length)
                f.read(4)  # skip CRC

                if ctype in ("tEXt", "iTXt", "zTXt"):
                    keyword, _, raw_text = data.partition(b"\x00")
                    keyword = keyword.decode("latin-1", errors="ignore")

                    # decompress if zTXt
                    if ctype == "zTXt":
                        try:
                            raw_text = zlib.decompress(raw_text[2:])  # skip compression flag + method
                        except Exception:
                            pass

                    text = raw_text.replace(b"\x00", b"").decode("utf-8", errors="ignore")

                    if keyword.lower() in ("prompt", "workflow"):
                        print(f"\n--- {file_path.name} :: {keyword} ---")
                        try:
                            parsed = json.loads(text)
                            print(json.dumps(parsed, indent=2, ensure_ascii=False).rstrip())
                        except json.JSONDecodeError:
                            print(text)

                if ctype == "IEND":
                    break
    except Exception as e:
        print(f"[!] Error parsing {file_path}: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Parse a single file
        file_path = Path(sys.argv[1])
        if file_path.exists():
            pretty_print_png_json(file_path)
        else:
            print(f"[!] File not found: {file_path}")
    else:
        # Default behavior: process all PNGs in images/
        folder = Path("images")
        for png in folder.glob("*.png"):
            pretty_print_png_json(png)


