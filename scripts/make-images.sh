#!/bin/bash
# make-images.sh — ポスター2枚から、投稿に使う4枚を作り直します。
#
# ポスターを差し替えたときに、これを1回動かせば済みます。
#
#   bash scripts/make-images.sh
#
# 読むもの（このどちらかがあれば動きます。jpg / jpeg / png / HEIC）
#   images/namaoke-1.*   1枚目のポスター
#   images/namaoke-2.*   2枚目のポスター
#
# 作るもの
#   images/feed-1.jpg  feed-2.jpg    1080×1350（縦4:5）  フィード投稿用
#   images/story-1.jpg story-2.jpg   1080×1920（縦9:16） ストーリーズ用
#
# ストーリーズは縦長なので、上下に帯を足します。帯の色は、ポスターの地の色に
# 近いものを選びます。既定はクリーム色（F7EFDC）です。変えたいときは:
#
#   bash scripts/make-images.sh --pad1 F7EFDC --pad2 3A2A1E

set -eu

cd "$(dirname "$0")/.."

PAD1="F7EFDC"   # 1枚目の帯の色
PAD2="F7EFDC"   # 2枚目の帯の色

while [ $# -gt 0 ]; do
  case "$1" in
    --pad1) PAD1="${2#\#}"; shift 2 ;;
    --pad2) PAD2="${2#\#}"; shift 2 ;;
    --help|-h) sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "知らない指定です: $1" >&2; exit 2 ;;
  esac
done

find_source() {
  for ext in jpg jpeg JPG JPEG png PNG heic HEIC; do
    [ -f "images/namaoke-$1.$ext" ] && { echo "images/namaoke-$1.$ext"; return 0; }
  done
  echo "images/namaoke-$1.（jpg か png）が見つかりません。" >&2
  echo "差し替えたいポスターを、その名前で images/ に置いてください。" >&2
  return 1
}

for i in 1 2; do
  eval PAD=\$PAD$i
  SRC="$(find_source "$i")"

  # フィード用：縦4:5。ポスターがすでに4:5なら、そのままJPEGにするだけです。
  sips -s format jpeg -s formatOptions 90 \
       --resampleHeightWidthMax 1350 \
       "$SRC" --out "images/feed-$i.jpg" >/dev/null 2>&1

  # ストーリー用：縦9:16。上下に帯を足して、切らずに全体を入れます。
  sips -s format jpeg -s formatOptions 90 \
       --padToHeightWidth 1920 1080 --padColor "$PAD" \
       "$SRC" --out "images/story-$i.jpg" >/dev/null 2>&1

  echo "$SRC"
  for out in "images/feed-$i.jpg" "images/story-$i.jpg"; do
    SIZE=$(sips -g pixelWidth -g pixelHeight "$out" 2>/dev/null | awk '/pixelWidth/{w=$2} /pixelHeight/{h=$2} END{print w "×" h}')
    KB=$(( $(stat -f%z "$out") / 1024 ))
    echo "  → $out  $SIZE  ${KB}KB"
  done
done

echo
echo "できました。中身を目で確かめてから、GitHub に送ってください。"
