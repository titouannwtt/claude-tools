# Third-party skill: unslop

This folder is a copy of the `unslop` skill by Damir Sokolovsky ([@heydamir](https://x.com/heydamir)),
creator of the Unslopping series.

- Source: https://github.com/heydamir/unslop (folder `skills/unslop`)
- Commit copied: `97daa3eb365670ea3f87ed85356cbfcee18105a5`
- License: Creative Commons Attribution 4.0 International (CC BY 4.0), full text in [`LICENSE`](LICENSE)
- Changes: none to the skill itself. Only this `NOTICE.md` and the upstream `LICENSE` file were added to the folder.

The rest of this repository is under the MIT license. That license does not apply to this folder: keep the
credit to Damir Sokolovsky in any copy or adaptation, and keep the `unslop by @heydamir` credit that the
story video carries.

## What the scripts do

Read before the copy was added:

- `scripts/snapshot.mjs` opens a URL or a local file in headless Chromium (Playwright), inlines the page's
  stylesheets and images, and writes one HTML file plus a `.live.png` screenshot at the output path you give.
- `scripts/story.mjs` serves the folder of the story file on `127.0.0.1` (random port), records frames into
  `.story-frames/` next to the story file, calls `ffmpeg` to build the video, then deletes that folder.

Neither script reads credentials or sends data anywhere other than the page being captured. Both need
Playwright with Chromium; the video also needs ffmpeg. Image generation is optional and the skill asks before
any paid generation.

## Updating

Replace the folder content with the new upstream `skills/unslop`, reread the two scripts, and update the commit
above.
