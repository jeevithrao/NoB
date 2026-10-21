const walks = [
  { id:1, icon:'🌸', t:'Sampige Road & the Agraharam', tag:'Malleshwaram', neighbourhood:'malleshwaram', meta:'2.3km · 90 min', bg:'#A28D6E', price:'₹249', stars:'★★★★★', rating:'4.9', distance:'2.3 km', duration:'90 min', start:'Sampige Road Metro Gate', theme:'Heritage', desc:'Start at the Sampige Road Metro Gate and wander Malleshwaram\'s old streets: Silk Weavers\' Lane and its ancient weaving traditions, the Kadu Malleshwara temple, the fragrant Flower Market and the traditional Agraharam Street. Five stops, told through audio as you walk.', stops:[{e:'🚇',n:'Starting Point',d:'Sampige Road Metro Gate'},{e:'🧵',n:'Silk Weavers\' Lane',d:'Ancient weaving traditions'},{e:'🛕',n:'Kadu Malleshwara',d:'18th-century Shiva temple'},{e:'🌸',n:'Flower Market',d:'The fragrant heart of Malleshwaram'},{e:'🏛️',n:'Agraharam Street',d:'Traditional Brahmin quarter'}] },
  { id:2, icon:'📚', t:'Gandhi Bazaar Book Lanes', tag:'Basavanagudi', neighbourhood:'basavanagudi', meta:'1.8km · 75 min', bg:'#2E2520', price:'₹199', stars:'★★★★★', rating:'4.8', distance:'1.8 km', duration:'75 min', start:'Gandhi Bazaar Main Arch', theme:'Culture', desc:'Begin under the Gandhi Bazaar arch, browse Book Street with some of the oldest bookshops in the city, then head to the famous Bull Temple and finish at Bugle Rock Park, a billion-year-old rock outcrop. Four stops, 1.8 km on foot.', stops:[{e:'🏛️',n:'Gandhi Bazaar Arch',d:'Built in 1900s'},{e:'📚',n:'Book Street',d:'Oldest bookshops in the city'},{e:'🐂',n:'Bull Temple',d:'Famous 16th-century temple'},{e:'🌳',n:'Bugle Rock Park',d:'Billion-year-old rock outcrop'}] },
  { id:3, icon:'🌳', t:'Cubbon Park Green Heart', tag:'Cubbon Park', neighbourhood:'cubbon-park', meta:'1.5km · 60 min', bg:'#B8A898', price:'Free', stars:'★★★★☆', rating:'4.7', distance:'1.5 km', duration:'60 min', start:'Cubbon Park Bandstand Gate', theme:'Nature', desc:'A free, easy stroll through Cubbon Park: the colonial bandstand gate, the State Library, trees over 150 years old and the Gothic-style High Court. Four stops over 1.5 km, at your own pace.', stops:[{e:'🎵',n:'Bandstand Gate',d:'1880s colonial bandstand'},{e:'📚',n:'State Library',d:'Built 1915, 100k volumes'},{e:'🌳',n:'Heritage Trees',d:'Trees over 150 years old'},{e:'⚖️',n:'High Court',d:'Gothic-style, built 1867'}] },
  { id:4, icon:'🏛️', t:'Colonial Cantonment Walk', tag:'MG Road', neighbourhood:'mg-road', meta:'2.0km · 80 min', bg:'#2E2520', price:'₹229', stars:'★★★★★', rating:'5.0', distance:'2.0 km', duration:'80 min', start:'MG Road Metro Exit 2', theme:'Colonial', desc:'Step out of MG Road Metro into colonial Bangalore: St. Mark\'s Cathedral, the Bowring Club and Windsor Manor, ending at the Cubbon Park gate. Five stops covering 2 km.', stops:[{e:'🚇',n:'MG Road Metro',d:'Start point'},{e:'⛪',n:'St. Mark\'s Cathedral',d:'1812 — oldest church'},{e:'🎳',n:'Bowring Club',d:'1868 — British social club'},{e:'🏨',n:'Windsor Manor',d:'1980s heritage hotel'},{e:'🌿',n:'Cubbon Park Gate',d:'End of walk'}] },
];

/* ───────────────────────────────────────────────────────────────────────────
   PER-WALK CONTENT  (merged into each walk below)
   OWNER REVIEW NEEDED. Everything marked PLACEHOLDER is a stand-in, not a verified fact:
   • coords      – approximate [lat, lng] per stop, in the same order as `stops`. PLACEHOLDER: set from
                   a map before launch. The route/distances on the Active Walk screen come from these.
   • difficulty  – derived from distance only (<= 1.8 km → Easy, otherwise Moderate). PLACEHOLDER.
   • language    – from the original "Audio guide (English + Kannada)" line.
   • sample      – the audio-sample teaser on Walk detail; walk 1 keeps the original title, the rest use
                   a stop name. PLACEHOLDER titles.
   • included / tags – walk 1 keeps the original lists; other walks reuse the included list and use a
                   neutral tag set (accessibility is "to be confirmed"). PLACEHOLDER.
   • reviewCount – PLACEHOLDER numbers.
   ─────────────────────────────────────────────────────────────────────────── */
const INCLUDED = ['Audio guide (English + Kannada)', 'Digital walk map', 'Historical notes PDF', 'Free cancellation 24h before']
const walkExtras = {
  1: {
    difficulty: 'Moderate', language: 'English · Kannada', reviewCount: 128,
    sample: { title: 'Silk weavers of Sampige Road', stop: 2 },
    included: INCLUDED,
    tags: ['Moderate fitness', 'Accessible pathways', 'Morning recommended', 'Family friendly'],
    coords: [[13.0014, 77.5704], [13.0030, 77.5710], [13.0066, 77.5716], [13.0050, 77.5700], [13.0042, 77.5688]],
  },
  2: {
    difficulty: 'Easy', language: 'English · Kannada', reviewCount: 86,
    sample: { title: 'Book Street', stop: 2 },
    included: INCLUDED,
    tags: ['Easy pace', 'Accessibility info to be confirmed'],
    coords: [[12.9455, 77.5718], [12.9448, 77.5705], [12.9419, 77.5680], [12.9432, 77.5664]],
  },
  3: {
    difficulty: 'Easy', language: 'English · Kannada', reviewCount: 54,
    sample: { title: 'State Library', stop: 2 },
    included: INCLUDED.filter(t => !t.startsWith('Free cancellation')),   // free walk: nothing to cancel
    tags: ['Easy pace', 'Accessibility info to be confirmed'],
    coords: [[12.9774, 77.5951], [12.9788, 77.5940], [12.9770, 77.5928], [12.9795, 77.5908]],
  },
  4: {
    difficulty: 'Moderate', language: 'English · Kannada', reviewCount: 97,
    sample: { title: "St. Mark's Cathedral", stop: 2 },
    included: INCLUDED,
    tags: ['Moderate fitness', 'Accessibility info to be confirmed'],
    coords: [[12.9756, 77.6068], [12.9743, 77.6007], [12.9722, 77.5997], [12.9770, 77.5985], [12.9755, 77.5960]],
  },
}
walks.forEach(w => {
  const x = walkExtras[w.id]
  Object.assign(w, { ...x, stops: w.stops.map((s, i) => ({ ...s, coords: x.coords[i] })) })
})

const neighbourhoods = [
  { slug:'malleshwaram', name:'Malleshwaram', emoji:'🌸', bg:'#A28D6E', tagline:'Old Bangalore · 1 walk available', description:'One of the oldest residential areas in Bangalore, established in the late 19th century. Named after the Malleshwara temple, this neighbourhood is famous for its silk weavers, flower markets, and traditional agraharam streets.' },
  { slug:'basavanagudi', name:'Basavanagudi', emoji:'🐂', bg:'#2E2520', tagline:'South Bangalore · 1 walk available', description:'Named after the famous Bull Temple, Basavanagudi is one of Bangalore\'s most charming old neighbourhoods. Gandhi Bazaar — its main market street — has been thriving since the 1920s.' },
  { slug:'cubbon-park', name:'Cubbon Park', emoji:'🌳', bg:'#A28D6E', tagline:'City centre · 1 walk available', description:'A 300-acre lung of the city created in 1870 by Colonel Richard Sankey. It houses the State Library, High Court, and dozens of heritage trees over a century old.' },
  { slug:'mg-road', name:'MG Road', emoji:'🏛️', bg:'#2E2520', tagline:'City centre · 1 walk available', description:'Once called South Parade, MG Road was the social hub of colonial Bangalore. Its tree-lined avenues, clubs, and churches are a testament to the city\'s British past.' },
];

const passportSlots = [
  { slug:'malleshwaram', name:'Malleshwaram', emoji:'🌸', collected:true, walkName:'Sampige Road Walk', date:'Aug 12, 2026' },
  { slug:'basavanagudi', name:'Basavanagudi', emoji:'🐂', collected:true, walkName:'Gandhi Bazaar Walk', date:'Jul 28, 2026' },
  { slug:'cubbon-park', name:'Cubbon Park', emoji:'🌳', collected:true, walkName:'Green Heart Walk', date:'Jul 4, 2026' },
  { slug:'mg-road', name:'MG Road', emoji:'🏛️', collected:false },
  { slug:'shivajinagar', name:'Shivajinagar', emoji:'🕌', collected:false },
  { slug:'jayanagar', name:'Jayanagar', emoji:'🏡', collected:false },
  { slug:'indiranagar', name:'Indiranagar', emoji:'☕', collected:false },
  { slug:'koramangala', name:'Koramangala', emoji:'🎭', collected:false },
  { slug:'whitefield', name:'Whitefield', emoji:'🏢', collected:false },
  { slug:'yelahanka', name:'Yelahanka', emoji:'🏰', collected:false },
  { slug:'rajajinagar', name:'Rajajinagar', emoji:'⚙️', collected:false },
  { slug:'fraser-town', name:'Fraser Town', emoji:'⛪', collected:false },
];

const bookingsData = {
  upcoming: [
    { id:'B001', walkName:'Colonial Cantonment Walk', neighbourhood:'MG Road', validUntil:'Dec 6, 2026', price:'₹229', icon:'🏛️', bg:'#2E2520' },
  ],
  past: [
    { id:'B002', walkName:'Sampige Road & the Agraharam', neighbourhood:'Malleshwaram', walkedOn:'Mon, Aug 12', price:'₹249', icon:'🌸', reviewed:true, bg:'#A28D6E' },
    { id:'B003', walkName:'Gandhi Bazaar Book Lanes', neighbourhood:'Basavanagudi', walkedOn:'Sun, Jul 28', price:'₹199', icon:'📚', reviewed:false, bg:'#2E2520' },
  ]
};

const notificationsData = [
  { id:1, type:'reminder', icon:'🔔', title:'Your walk is ready when you are', subtitle:'Colonial Cantonment Walk — MG Road', time:'2h ago', unread:true },
  { id:2, type:'confirmed', icon:'✅', title:'You\'re in!', subtitle:'Colonial Cantonment Walk — valid until Dec 6', time:'3h ago', unread:true },
  { id:3, type:'new', icon:'🗺️', title:'New walk: Yelahanka Fort Trail', subtitle:'North Bangalore · 2.8km · ₹279', time:'Yesterday', unread:false },
  { id:4, type:'review', icon:'⭐', title:'How was your walk?', subtitle:'Leave a review for Gandhi Bazaar Book Lanes', time:'1 week ago', unread:false },
];


// MOCK reviews. Each belongs to one walk (walkId). The first four are the originals; the rest are PLACEHOLDERS.
const reviews = [
  { walkId:1, name:'Ananya R.', tour:'Sampige Road walk', stars:'★★★★★', text:'Absolutely loved it. The audio felt like walking with a friend who knew everything.', color:'#A28D6E' },
  { walkId:2, name:'Kiran M.',  tour:'Gandhi Bazaar walk', stars:'★★★★★', text:'Discovered lanes I\'ve passed a hundred times but never actually seen. Magical.', color:'#2E2520' },
  { walkId:4, name:'Deepa S.', tour:'Colonial Cantonment', stars:'★★★★☆', text:'Perfect Sunday activity. Audio quality was excellent and the pacing was just right.', color:'#2E2520' },
  { walkId:3, name:'Rahul T.', tour:'Cubbon Park', stars:'★★★★★', text:'Even the free walk was worth it. Can\'t wait to try the paid ones.', color:'#B8A898' },
  { walkId:1, name:'Meera K.', tour:'Sampige Road walk', stars:'★★★★★', text:'Easy to follow, and the stories made me look up at buildings I always walked past.', color:'#2E2520' },
  { walkId:2, name:'Suresh P.', tour:'Gandhi Bazaar walk', stars:'★★★★☆', text:'A relaxed route with plenty of places to stop. I went at my own pace.', color:'#A28D6E' },
  { walkId:3, name:'Nisha V.', tour:'Cubbon Park', stars:'★★★★☆', text:'A calm walk. The audio kicked in right when I reached each stop.', color:'#2E2520' },
  { walkId:4, name:'Arjun D.', tour:'Colonial Cantonment', stars:'★★★★★', text:'Great way to see the centre of the city differently.', color:'#B8A898' },
];

export { walks, neighbourhoods, passportSlots, bookingsData, notificationsData, reviews };
