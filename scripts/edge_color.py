#!/usr/bin/env python3
"""ポスターの上端の色を測って、16進6桁で出します。

ストーリーズ用に足す帯の色を、ポスターの地の色に自動で合わせるために使います。
手で色を選ばなくてよくなるので、ポスターを差し替えても継ぎ目が出ません。

  python3 scripts/edge_color.py images/namaoke-2.png
  → FEFEFE

jpg でも HEIC でも動きます（いったん png に直してから読みます）。
"""

import struct
import subprocess
import sys
import tempfile
import zlib
from collections import Counter
from pathlib import Path

FALLBACK = "F7EFDC"  # 読めなかったときのクリーム色


def to_png(path):
    if path.suffix.lower() == ".png":
        return path, None
    tmp = Path(tempfile.mkdtemp()) / "edge.png"
    subprocess.run(["sips", "-s", "format", "png", str(path), "--out", str(tmp)],
                   check=True, capture_output=True)
    return tmp, tmp


def top_row(path, nrows=4):
    """PNG の上から数行だけ復号します（全部読む必要はありません）。"""
    d = path.read_bytes()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG ではありません")

    pos, idat, hdr = 8, b"", None
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        if typ == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", d[pos + 8:pos + 8 + ln])
        elif typ == b"IDAT":
            idat += d[pos + 8:pos + 8 + ln]
            if len(idat) > 1 << 20:
                break  # 上の数行に足りる分だけあれば十分です
        elif typ == b"IEND":
            break
        pos += 12 + ln

    w, h, depth, ctype = hdr[0], hdr[1], hdr[2], hdr[3]
    if depth != 8 or ctype not in (2, 6):
        raise ValueError(f"この形式は読めません（depth={depth} type={ctype}）")

    ch = 3 if ctype == 2 else 4
    stride = w * ch
    raw = zlib.decompressobj().decompress(idat, (stride + 1) * nrows)

    prev, line = bytearray(stride), bytearray(stride)
    for r in range(min(nrows, len(raw) // (stride + 1))):
        f = raw[r * (stride + 1)]
        line = bytearray(raw[r * (stride + 1) + 1:(r + 1) * (stride + 1)])
        for x in range(stride):
            a = line[x - ch] if x >= ch else 0
            b = prev[x]
            c = prev[x - ch] if x >= ch else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
    return w, ch, bytes(line)


def main():
    src = Path(sys.argv[1])
    tmp = None
    try:
        png, tmp = to_png(src)
        w, ch, row = top_row(png)
        # いちばん多く出てくる色を取ります。端の影や紙の質感に引きずられないためです。
        counts = Counter((row[x * ch], row[x * ch + 1], row[x * ch + 2]) for x in range(w))
        r, g, b = counts.most_common(1)[0][0]
        print(f"{r:02X}{g:02X}{b:02X}")
    except Exception as e:
        print(FALLBACK)
        print(f"上端の色を測れなかったので {FALLBACK} を使います（{e}）", file=sys.stderr)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


if __name__ == "__main__":
    main()
