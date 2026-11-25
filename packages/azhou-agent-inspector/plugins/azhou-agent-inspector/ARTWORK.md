Azhou artwork © 小亮 (阿舟 / Azhou), CC BY-NC-ND 4.0. The bundled 120px WebP is a full-frame size and format conversion of the [approved Hub entry portrait](https://github.com/TeFuirnever/azhou-ai-hub/blob/5f56f0db96fca10514f3865ceeb8ec00526161b8/assets/azhou/entry-avatar.png). See the [license](https://creativecommons.org/licenses/by-nc-nd/4.0/).

The Codex panel backdrop is a 640px-wide WebP conversion of the [approved Agent Skin wallpaper](https://github.com/TeFuirnever/azhou-ai-hub/blob/5f56f0db96fca10514f3865ceeb8ec00526161b8/assets/azhou/wallpaper-scene-q-v3.png). The conversion preserves the full composition. The panel applies positioning and a readability scrim in CSS.

From the repository root, regenerate the packaged backdrop with ImageMagick.

```sh
magick assets/azhou/wallpaper-scene-q-v3.png -resize 640x -strip -quality 84 \
  packages/azhou-agent-inspector/plugins/azhou-agent-inspector/wallpaper.webp
```
