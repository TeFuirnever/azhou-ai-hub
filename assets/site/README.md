# Site hero derivatives

WebP derivatives of `../github/readme-hero.png` used by the documentation
site (`site/`). The source artwork and its license live in `assets/github/`
(see `packages/agent-skin/assets/azhou/NOTICE.md`); these files carry the
same terms. Regenerate after changing the source artwork, then bump the
`?v=` cache parameter in `site/index.njk` and `site/zh/index.njk`:

    sips -Z 640 ../github/readme-hero.png --out /tmp/hero-640.png
    cwebp -q 82 ../github/readme-hero.png -o hero.webp
    cwebp -q 82 /tmp/hero-640.png -o hero-640.webp
