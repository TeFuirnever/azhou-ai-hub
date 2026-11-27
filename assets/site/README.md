# Site artwork

## Hero

Historical WebP derivatives of [the README hero](../github/readme-hero.png) (`hero.webp`, `hero-640.webp`) and active landing-page WebP derivatives (`workspace-1672.webp`, `workspace-836.webp`) of [the workspace illustration](../azhou/wallpaper-scene-q-v3.png). Their terms follow the [Azhou artwork notice](../azhou/NOTICE.md). Social previews (`og:image` / `twitter:image`) continue to use the PNG workspace illustration.

Regenerate workspace WebPs from the repository root with Python 3 and Pillow:

```sh
python3 - <<'EOF'
from PIL import Image
src = Image.open("assets/azhou/wallpaper-scene-q-v3.png")
src.save("assets/site/workspace-1672.webp", format="WEBP", quality=82, method=6)
src.resize((836, round(src.height * 836 / src.width)), Image.Resampling.LANCZOS).save(
    "assets/site/workspace-836.webp", format="WEBP", quality=82, method=6
)
EOF
```

## Avatar and icons

The official site uses two resizes of the [Azhou Bot entry portrait](../azhou/entry-avatar.png) with the maintainer's permission. `azhou-avatar.png` (64×64) supplies the navigation, Ask Azhou install heading, and favicon. `apple-touch-icon.png` (180×180) supplies the Home Screen icon.

Azhou artwork © 小亮 (阿舟 / Azhou), CC BY-NC-ND 4.0. See the [Azhou artwork notice](../azhou/NOTICE.md).

Regenerate the PNGs from the repository root with Python 3 and Pillow 13.0.0 with zlib-ng 2.3.3:

```sh
python3 - <<'EOF'
from PIL import Image

with Image.open("assets/azhou/entry-avatar.png") as source:
    for name, size in (("azhou-avatar", 64), ("apple-touch-icon", 180)):
        source.resize((size, size), Image.Resampling.LANCZOS).save(
            f"assets/site/{name}.png", format="PNG", compress_level=9
        )
EOF
```
