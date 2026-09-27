# The website

oma-solorpg's page: plain HTML, CSS and JavaScript, no build step. `make site` serves it on http://localhost:8000, and `.github/workflows/pages.yml` publishes this folder to GitHub Pages on every push to `main` that touches it (set Pages to "GitHub Actions" once, in the repository's settings).

## The trailers

Drop the two cuts into `media/`:

```
media/oma-solorpg-45s.mp4
media/oma-solorpg-15s.mp4
```

Until a file is there, its tab shows a placeholder with the path it's waiting for. H.264 in an MP4 plays everywhere; keep each under about 20 MB so the page stays quick (`ffmpeg -i in.mp4 -c:v libx264 -crf 24 -preset slow -movflags +faststart -c:a aac -b:a 128k out.mp4`).

## Where the pictures come from

Every screenshot is the plugin's real QML, rendered offscreen against real engine state, not a mockup:

- The Red Tusk Hall (`img/red-*`) with `tests/qml/render.py`'s scenario, the adventure this repository ships.
- The Sinking Tower and Alone in Deepfall Breach (`img/tower-*`, `img/breach-*`, `img/table-*`) from the author's own packs, compiled from books the author owns with `make rules` and `make adventure`. The packs are not in this repository. The screenshots show names, titles, the engine's own text art and its dice; the GM's lines in them were written for the screenshots, and a monster's attack table text was kept out of frame.
- `img/extract-table.webp` is `solo extract`'s picture of a table page from the made-up rulebook in `tests/test_rules_import.py`.

The faces in `art.js` come from `solo/portrait.py` and `packs/dragonbane/art.toml`, one per kin and mood. Regenerate the file rather than editing it.

## Before publishing

- `og:url` and `og:image` in `index.html` assume `https://cabral.github.io/oma-solorpg/`. Change both for another address.
- The shelf section shows Free League's adventures by name, with screenshots of play. It credits them and says the packs stay private; check it against the license's terms before it goes out.

There is also a door somewhere on the page that wasn't there before. Its code is in `secret.js`.
