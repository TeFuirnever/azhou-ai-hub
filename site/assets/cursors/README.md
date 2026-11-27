# Azhou Web Cursor Stills

Static 1× (`32×32`) and 2× (`64×64`) PNG cursor stills extracted from [Azhou Double Hug 3.6.1](../../../assets/cursors/azhou-double-hug/Azhou-Double-Hug-3.6.1.cape).

## Source mapping

| File | Cape key | Frame | CSS hotspot |
| --- | --- | --- | --- |
| `arrow.png` / `arrow@2x.png` | `com.apple.coregraphics.Arrow` | `0` | `3 3` |
| `pointer.png` / `pointer@2x.png` | `com.apple.cursor.13` | `0` | `3 3` |
| `text.png` / `text@2x.png` | `com.apple.coregraphics.IBeam` | `0` | `16 16` |
| `grab.png` / `grab@2x.png` | `com.apple.cursor.12` | `0` | `16 21` |
| `grabbing.png` / `grabbing@2x.png` | `com.apple.cursor.11` | `1` | `16 21` |

## Regenerate and check

From the repository root (requires Python 3 and Pillow):

```sh
python3 site/scripts/extract-cursors.py
python3 site/scripts/extract-cursors.py --check
```

## Rights

Extraction script is MIT-licensed with the repository. The Azhou cursor artwork is © 小亮 (阿舟 / Azhou), CC BY-NC-ND 4.0 — see [assets/azhou/NOTICE.md](../../../assets/azhou/NOTICE.md) and [TRADEMARKS.md](../../../TRADEMARKS.md).
