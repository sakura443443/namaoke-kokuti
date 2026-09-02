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
# ポスターは切りません。決まった形に足りないぶんは、帯で埋めます。
# （Instagram は 4:5 より縦長の絵を勝手に切ります。下の会場名が消える事故を防ぎます）
#
# 帯の色は、ポスターの上端を実際に測って自動で合わせます。継ぎ目が出ません。
# 気に入らないときだけ、手で指定できます:
#
#   bash scripts/make-images.sh --pad1 FCECD6 --pad2 FEFEFE

set -eu

cd "$(dirname "$0")/.."

PAD1=""   # 空なら、ポスターの上端を測って自動で決めます
PAD2=""

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
  SRC="$(find_source "$i")"

  eval PAD=\$PAD$i
  if [ -z "$PAD" ]; then
    PAD="$(python3 scripts/edge_color.py "$SRC")"
  fi

  # フィード用：縦4:5。Instagram はこれより縦長・横長だと上下左右を勝手に切ります。
  # ポスターは切らずに、足りないぶんを帯で埋めます。
  sips -s format jpeg -s formatOptions 90 \
       --padToHeightWidth 1350 1080 --padColor "$PAD" \
       "$SRC" --out "images/feed-$i.jpg" >/dev/null 2>&1

  # ストーリー用：縦9:16。上下に帯を足して、切らずに全体を入れます。
  sips -s format jpeg -s formatOptions 90 \
       --padToHeightWidth 1920 1080 --padColor "$PAD" \
       "$SRC" --out "images/story-$i.jpg" >/dev/null 2>&1

  echo "$SRC  （帯の色 #$PAD）"
  for out in "images/feed-$i.jpg" "images/story-$i.jpg"; do
    SIZE=$(sips -g pixelWidth -g pixelHeight "$out" 2>/dev/null | awk '/pixelWidth/{w=$2} /pixelHeight/{h=$2} END{print w "×" h}')
    KB=$(( $(stat -f%z "$out") / 1024 ))
    echo "  → $out  $SIZE  ${KB}KB"
  done
done

echo
echo "できました。中身を目で確かめてから、GitHub に送ってください。"
