# Azhou Double Hug 3.6.1

A standalone Mousecape theme for macOS with 41 cursor states and 32 px and 64 px image strips. The ordinary arrow is still. Links and waiting use short loops, and the grab state shows Azhou hugging her tail.

![Azhou Double Hug in dark and light contexts at 3× and 1×](preview.png)

## Install

1. Import [Azhou-Double-Hug-3.6.1.cape](Azhou-Double-Hug-3.6.1.cape) in Mousecape.
2. Select **百变阿舟 · 抱一下 3.6.1** and choose **Apply**.
3. Check the arrow and text selection in Finder or a document. To revert, select your previous cape and choose **Apply**, or use Mousecape to restore the system cursors.

[Import 3.6.1](Azhou-Double-Hug-3.6.1.cape) 后，选中「百变阿舟 · 抱一下 3.6.1」并点击 Apply。可以重新应用原来的皮肤，或用 Mousecape 恢复系统指针。

## Rebuild

With Python 3 and Pillow 13.0.0, run from this directory:

```sh
python3 build.py --output /tmp/Azhou-Double-Hug-3.6.1.cape
cmp Azhou-Double-Hug-3.6.1.cape /tmp/Azhou-Double-Hug-3.6.1.cape
```

Both source atlases are required. The builder draws the symbols and assembles the 1× and 2× strips without fonts or network access. Byte-for-byte results were checked with CPython 3.15.2, Pillow 13.0.0 and its bundled zlib-ng 1.3.1. Different encoders may produce different PNG bytes.

The repository's unit suite checks the delivered file's identifier, role set, animation timing, hotspots and PNG strip dimensions. Mousecape export and desktop appearance are separate checks.

## Rights

Code follows the repository MIT license. Source atlases, preview and artwork embedded in the cape are © 2026 小亮 (阿舟 / Azhou), CC BY-NC-ND 4.0. See the [artwork license](../../../packages/agent-skin/assets/azhou/LICENSE) and [brand terms](../../../TRADEMARKS.md).

未经许可，请勿修改并再分发阿舟素材或用于商业用途。阿舟名称与形象属于作者品牌。
