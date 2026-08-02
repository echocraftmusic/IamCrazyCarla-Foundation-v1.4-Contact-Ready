# READ BEFORE EDITING — IamCrazyCarla.com

## Do not break these systems
- Keep `index.html`, `css`, `js`, `data`, `images`, `scripts`, and `.github/workflows` paths unchanged.
- Do not rename images without updating `data/gallery.json`.
- Do not place Carla's Google or YouTube password anywhere in this repository.
- The YouTube updater reads only public channel information from `@10aahfro`.
- The scheduled workflow writes to `data/youtube-videos.json` every Wednesday evening Eastern (UTC schedule noted in the workflow).
- Preserve both `data-theme="dark"` and the theme toggle JavaScript.
- Test desktop, tablet, and phone before publishing.

## Gallery
The visible gallery is driven by `data/gallery.json`. The included `admin/gallery.html` exports a replacement JSON file. A secure direct-publish admin needs hosting credentials and must not be simulated with a visible JavaScript password.

## Contact form
The form currently uses FormSubmit and may require the owner to confirm the destination email once. Replace it later if a different form service is chosen.
