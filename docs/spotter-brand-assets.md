# Spotter asset provenance — P07.3

Verified 2026-11-06 against https://spotter.ai/ and https://spotter.ai/tms. Product identity cross-checked with https://apps.apple.com/us/app/spotter-ai/id1670506993 and https://play.google.com/store/apps/details?id=com.spotter.ai (Spotter Labs). No private/internal design system claimed.

| Asset | Direct source | Verified format/dimensions | Inspection / usage | Download / local path |
|---|---|---|---|---|
| Light wordmark | https://spotter.ai/static/media/spotter.ai.f4811cd7bfcabdaadfb7.webp | WebP RGBA, 640×158 | White thin wordmark and colored dots, transparent; needs dark background; unsuitable for current white header | Downloaded to temporary inspection storage only; not bundled |
| Official icon | https://spotter.ai/favicon-96x96.png | PNG RGBA, 96×96 | Transparent red/teal/pale-dot symbol; visually inspected | Downloaded to temporary inspection storage only; not bundled |
| SVG favicon lead | https://spotter.ai/favicon.svg | Homepage metadata references it; content not independently verified | Not used | Not downloaded |
| Apple touch icon lead | https://spotter.ai/apple-touch-icon.png | Homepage metadata references it; dimensions not independently verified | Not used | Not downloaded |

Originating page for all candidates: official homepage. Metadata also includes favicon.ico and manifest.json. No verified compact dark wordmark or public brand kit was found in the inspected material. No official SVG was fabricated. Existing application favicon remains unchanged.

## Permission and fallback

The official [terms](https://spotter.ai/terms-and-services), sections “Your rights to use the Spotter Service” and “Spotter’s Proprietary Rights”, reserve brand-feature ownership and do not grant commercial or noncommercial brand-feature usage rights; redistribution permission is not established. No separate public media license was located in inspected homepage/TMS metadata or focused official-domain search. Therefore neither image is redistributed in public assets. Header uses restrained plain text “spotter.ai” with an assessment-prototype designation; this identifies assessment context, not endorsement or a licensed logo. Permission should be resolved before external publication.

## Typography

Homepage HTML directly references Matter-Regular.woff2 and Matter-SemiBold.woff2, and Google Fonts DM Sans weights300–800/Open Sans. These are observed marketing-site choices, not internal product standards. Matter is not used: no repository license. DM Sans OFL source: https://github.com/google/fonts/blob/main/ofl/dmsans/OFL.txt. Font bundling/verification outcome is recorded below. System fallback never initiates a third-party font request.

## Tokens

Teal #008080, accent #40e0d0, soft #d9f9f6 and ink #252e3c are task-supplied public-site leads adapted for this UI, not asserted official tokens. Current homepage typography was verified from HTML; exact CSS palette could not initially be retrieved during network failures. Operational severity palette is independent; text labels accompany color. Main button white/teal contrast is checked separately in browser evidence. No decorative company symbol recreated.

DM Sans is now bundled locally: `frontend/public/fonts/dm-sans-latin.woff2`, variable normal weights100–900, from Fontsource Variable DM Sans5.3.0 (`https://registry.npmjs.org/@fontsource-variable/dm-sans/-/dm-sans-5.3.0.tgz`, package file `files/dm-sans-latin-wght-normal.woff2`). Actual package LICENSE inspected and retained as `frontend/public/fonts/OFL-DM-Sans.txt`; SIL OFL1.1 permits redistribution with notice/license. Google Fonts upstream OFL was independently downloaded and inspected. No npm dependency added. One Latin subset, normal style only; system fallback covers unsupported scripts. No external font-service requests or Matter/Inter binaries. Initial DNS failures were bypassed for downloading by a temporary curl resolver override, without system/network configuration changes.

## Final sign-off requirements — 2026-11-07

Official terms were rechecked at https://spotter.ai/terms-and-services; the brand-feature clause still supplies no reuse permission. Before replacing the assessment text fallback, obtain written authorization or an applicable official asset license covering the repository, hosted assessment and walkthrough. Retain that permission/provenance with the asset. Request an approved dark-on-light wordmark or suitable vector from Spotter; the verified white 640×158 WebP needs an approved dark surface and must not be recolored or reconstructed without approval. The 96px icon is not a replacement wordmark. Preserve aspect ratio, required clear space/minimum size and approved colors, use accessible alternative text, and retain the assessment designation without implying endorsement. Recheck the delivered file type, transparency, resolution and license before bundling; avoid unapproved hotlinking. No official logo asset is currently included. The fallback is accepted for this milestone; publication identity review remains separate from implementation acceptance.
