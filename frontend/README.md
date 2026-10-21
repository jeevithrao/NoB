# NoB — Neighbourhoods of Bangalore (React)

React + Vite port of NOB_Final4.html. All 17 screens, the same CSS (copied verbatim), the same data, animations and interactions.

    npm install
    npm run dev

## Place photos
Drop images into `public/images/` (or paste URLs into `src/images.js`):

| Place        | Main photo           | Gallery (detail page)                                   |
|--------------|----------------------|---------------------------------------------------------|
| Malleshwaram | malleshwaram.jpg     | malleshwaram-1.jpg, -2.jpg, -3.jpg                      |
| Basavanagudi | basavanagudi.jpg     | basavanagudi-1.jpg, -2.jpg, -3.jpg                      |
| Cubbon Park  | cubbon-park.jpg      | cubbon-park-1.jpg, -2.jpg, -3.jpg                       |
| MG Road      | mg-road.jpg          | mg-road-1.jpg, -2.jpg, -3.jpg                           |

Photos are loaded from each place's Wikipedia article automatically (no key). Put your own files above to override them. Missing photos fall back to the emoji tile.

## Layout modes
- Desktop: the app is shown inside a 320×680 phone frame with the prototype nav row above it.
- Phones (viewport ≤ 600px wide): the app fills the screen (100dvh), respects safe-area insets, and the frame, notch, caption and prototype nav row are hidden.

## Things to verify before launch
- Stop coordinates (`coords` in `src/data.js`), difficulty labels, audio-sample titles, tags and review counts are placeholders.
- Active Walk uses Leaflet + OpenStreetMap tiles (no API key). Audio playback is simulated.
- Settings → Photo credits lists the Wikipedia article behind each place photo.
