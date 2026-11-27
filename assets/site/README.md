# Site hero derivatives

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
