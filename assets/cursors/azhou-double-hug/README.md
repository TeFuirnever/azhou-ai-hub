# Azhou Double Hug 3.3.1

A macOS Mousecape cursor candidate featuring Azhou. It contains 41 cursor states, 32/64 px representations, and at most 24 frames per animated state.

Import [Azhou-Double-Hug-3.3.1.cape](Azhou-Double-Hug-3.3.1.cape) into Mousecape, select it, and choose Apply. The normal arrow is static. Grab, link and wait states include animation.

![Cursor preview](preview.png)

The preview shows the shared 3.3 artwork. In 3.3.1 the normal arrow is static and animation strips are limited to 24 frames.

## Verification and acceptance

Decoded image dimensions, frame counts and hotspots were checked. The installed 3.3.1 images match the delivered artifact, and Mousecape records this selected identifier.

Desktop appearance in Finder remains pending visual acceptance after the user reported an earlier version mismatch. Mousecape's Applied label alone does not establish system-wide display. This candidate has no Hub-managed installer.

## Rebuild

On macOS, with Python 3 and Pillow installed, run Python on build.py in this directory. The two source atlases are required build inputs. Rebuilding reproduces the delivered cape byte for byte in the tested environment.

The atlases were generated for this cursor task and selected by the maintainer. Other experimental versions are excluded.

## Rights

Code follows the repository MIT license. Images, source atlases and artwork embedded in the cape are © 2026 小亮 (阿舟 / Azhou), CC BY-NC-ND 4.0. See the [artwork license](../../../packages/agent-skin/assets/azhou/LICENSE) and [brand terms](../../../TRADEMARKS.md).

未经许可，请勿修改并再分发阿舟素材或用于商业用途。阿舟名称与形象属于作者品牌。
