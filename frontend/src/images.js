// Photos for each place.
// Order of lookup for every photo slot:
//   1. your own file in public/images/  (<slug>.jpg, <slug>-1.jpg, <slug>-2.jpg, <slug>-3.jpg)
//   2. a URL you paste into REMOTE below, e.g. 'cubbon-park': 'https://…/photo.jpg'
//   3. the real photo from the place's Wikipedia article (loaded in the browser, no API key)
//   4. the original coloured emoji tile, if none of the above load
// Slots 0-3 map to the main photo + the 3 gallery photos on the walk detail page.
export const REMOTE = {}

// Wikipedia article titles whose lead photo is used for each slot (index = slot)
export const WIKI = {
  malleshwaram: ['Kadu_Malleshwara_Temple', 'Malleshwaram', 'Nandishwara_Teertha_Temple', 'Kadu_Malleshwara_Temple'],
  basavanagudi: ['Dodda_Basavana_Gudi', 'Basavanagudi', 'Dodda_Ganeshana_Gudi', 'Bugle_Rock'],
  'cubbon-park': ['Cubbon_Park', 'Attara_Kacheri', 'Government_Museum,_Bangalore', 'Cubbon_Park'],
  'mg-road': ["St._Mark's_Cathedral,_Bangalore", 'M_G_Road,_Bangalore', 'Cubbon_Park', 'Attara_Kacheri'],
}

const base = import.meta.env.BASE_URL
export const localPhoto = (slug, n = 0) => `${base}images/${slug}${n ? '-' + n : ''}.jpg`

const cache = new Map()
// Resolves to { big, small } image URLs for a Wikipedia article, or null
export function wikiImage(title) {
  if (!cache.has(title)) {
    const p = fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title)}`)
      .then(r => (r.ok ? r.json() : null))
      .then(j => {
        const s = j && j.thumbnail && j.thumbnail.source
        return s ? { big: s.replace(/\/[0-9]+px-/, '/800px-'), small: s } : null
      })
      .catch(() => null)
    cache.set(title, p)
    // a failed lookup (offline, server error, no photo yet) is not remembered: the next attempt asks again
    p.then(v => { if (!v && cache.get(title) === p) cache.delete(title) })
  }
  return cache.get(title)
}

// Alt text for a photo slot: the Wikipedia article title it comes from
export const altFor = (slug, n = 0) => {
  const t = (WIKI[slug] || [])[n]
  return t ? t.replace(/_/g, ' ') : slug.replace(/-/g, ' ')
}
