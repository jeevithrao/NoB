"""Demo content shared by app.seed and the placeholder-audio generator.

It mirrors the frontend prototype (nob-react `src/data.js`): the same four walks,
neighbourhoods, prices and passport slots, so the two can be connected without
changing screens.

PLACEHOLDER CONTENT: stop coordinates, difficulty, tags and all narration text are
stand-ins (the frontend README says the same about its coordinates). The owner must
verify coordinates on a map and replace the narration with real scripts/recordings
before launch. Photos are intentionally left empty for now: the frontend falls back
to its own image source until owned or licensed photos are added.
"""

INCLUDED = [
    "Audio guide (English + Kannada)",
    "Digital walk map",
    "Historical notes PDF",
    "Free cancellation until you start your walk (within 14 days)",
]

# Neighbourhoods. The first four have a walk; the rest are locked passport slots
# ("Not yet explored") until a walk is added there.
NEIGHBOURHOODS = [
    {
        "name": "Malleshwaram", "slug": "malleshwaram", "emoji": "🌸",
        "tagline": "Old Bangalore",
        "description": (
            "One of the oldest residential areas in Bangalore, established in the late 19th century. Named after the "
            "Malleshwara temple, this neighbourhood is famous for its silk weavers, flower markets, and traditional "
            "agraharam streets."
        ),
        "centroid_lat": 13.0035, "centroid_lng": 77.5700,
    },
    {
        "name": "Basavanagudi", "slug": "basavanagudi", "emoji": "🐂",
        "tagline": "South Bangalore",
        "description": (
            "Named after the famous Bull Temple, Basavanagudi is one of Bangalore's most charming old neighbourhoods. "
            "Gandhi Bazaar — its main market street — has been thriving since the 1920s."
        ),
        "centroid_lat": 12.9440, "centroid_lng": 77.5690,
    },
    {
        "name": "Cubbon Park", "slug": "cubbon-park", "emoji": "🌳",
        "tagline": "City centre",
        "description": (
            "A 300-acre lung of the city created in 1870 by Colonel Richard Sankey. It houses the State Library, "
            "High Court, and dozens of heritage trees over a century old."
        ),
        "centroid_lat": 12.9780, "centroid_lng": 77.5930,
    },
    {
        "name": "MG Road", "slug": "mg-road", "emoji": "🏛️",
        "tagline": "City centre",
        "description": (
            "Once called South Parade, MG Road was the social hub of colonial Bangalore. Its tree-lined avenues, "
            "clubs, and churches are a testament to the city's British past."
        ),
        "centroid_lat": 12.9750, "centroid_lng": 77.6000,
    },
    {"name": "Shivajinagar", "slug": "shivajinagar", "emoji": "🕌", "tagline": "Coming soon"},
    {"name": "Jayanagar", "slug": "jayanagar", "emoji": "🏡", "tagline": "Coming soon"},
    {"name": "Indiranagar", "slug": "indiranagar", "emoji": "☕", "tagline": "Coming soon"},
    {"name": "Koramangala", "slug": "koramangala", "emoji": "🎭", "tagline": "Coming soon"},
    {"name": "Whitefield", "slug": "whitefield", "emoji": "🏢", "tagline": "Coming soon"},
    {"name": "Yelahanka", "slug": "yelahanka", "emoji": "🏰", "tagline": "Coming soon"},
    {"name": "Rajajinagar", "slug": "rajajinagar", "emoji": "⚙️", "tagline": "Coming soon"},
    {"name": "Fraser Town", "slug": "fraser-town", "emoji": "⛪", "tagline": "Coming soon"},
]


def _stop(name, blurb, icon, lat, lng, narration, audio):
    return {
        "name": name, "blurb": blurb, "icon": icon, "lat": lat, "lng": lng,
        "trigger_radius_m": 30, "narrative_text": narration, "audio_filename": audio,
    }


TOURS = [
    {
        "name": "Sampige Road & the Agraharam",
        "neighbourhood": "malleshwaram",
        "is_featured": True,
        "theme": "Heritage", "difficulty": "Moderate",
        "start_point": "Sampige Road Metro Gate",
        "tags": ["Moderate fitness", "Accessible pathways", "Morning recommended", "Family friendly"],
        "includes": INCLUDED, "languages": ["English", "Kannada"], "gallery_images": [],
        "description": (
            "Start at the Sampige Road Metro Gate and wander Malleshwaram's old streets: Silk Weavers' Lane and its "
            "ancient weaving traditions, the Kadu Malleshwara temple, the fragrant Flower Market and the traditional "
            "Agraharam Street. Five stops, told through audio as you walk."
        ),
        "city": "Bangalore", "cover_image": None,
        "duration_min": 90, "distance_km": 2.3, "price_paise": 24900, "is_free": False,
        "preview_audio_filename": "previews/malleshwaram.mp3",
        "preview_audio_title": "Silk weavers of Sampige Road",
        "preview_text": "Welcome to Malleshwaram. In a moment you will hear how the silk weavers of Sampige Road shaped this neighbourhood.",
        "stops": [
            _stop("Starting Point", "Sampige Road Metro Gate", "🚇", 13.0014, 77.5704,
                  "Welcome. You are standing at the Sampige Road Metro Gate, where our walk through Malleshwaram begins.",
                  "malleshwaram/01-start.mp3"),
            _stop("Silk Weavers' Lane", "Ancient weaving traditions", "🧵", 13.0030, 77.5710,
                  "This lane is known for its weaving traditions. Listen for the looms and look for the fabric on display.",
                  "malleshwaram/02-silk-weavers.mp3"),
            _stop("Kadu Malleshwara", "18th-century Shiva temple", "🛕", 13.0066, 77.5716,
                  "The Kadu Malleshwara temple gives the neighbourhood its name. It is an eighteenth century Shiva temple.",
                  "malleshwaram/03-kadu-malleshwara.mp3"),
            _stop("Flower Market", "The fragrant heart of Malleshwaram", "🌸", 13.0050, 77.5700,
                  "You will smell the Flower Market before you see it. Jasmine, marigold and rose change hands here every morning.",
                  "malleshwaram/04-flower-market.mp3"),
            _stop("Agraharam Street", "Traditional Brahmin quarter", "🏛️", 13.0042, 77.5688,
                  "Agraharam Street is a traditional quarter of houses with deep verandas, built around the temple.",
                  "malleshwaram/05-agraharam.mp3"),
        ],
    },
    {
        "name": "Gandhi Bazaar Book Lanes",
        "neighbourhood": "basavanagudi",
        "is_featured": True,
        "theme": "Culture", "difficulty": "Easy",
        "start_point": "Gandhi Bazaar Main Arch",
        "tags": ["Easy pace", "Accessibility info to be confirmed"],
        "includes": INCLUDED, "languages": ["English", "Kannada"], "gallery_images": [],
        "description": (
            "Begin under the Gandhi Bazaar arch, browse Book Street with some of the oldest bookshops in the city, then "
            "head to the famous Bull Temple and finish at Bugle Rock Park, a billion-year-old rock outcrop. Four stops, "
            "1.8 km on foot."
        ),
        "city": "Bangalore", "cover_image": None,
        "duration_min": 75, "distance_km": 1.8, "price_paise": 19900, "is_free": False,
        "preview_audio_filename": "previews/basavanagudi.mp3",
        "preview_audio_title": "Book Street",
        "preview_text": "Welcome to Gandhi Bazaar. Next, a taste of Book Street and its old bookshops.",
        "stops": [
            _stop("Gandhi Bazaar Arch", "Built in 1900s", "🏛️", 12.9455, 77.5718,
                  "You are under the Gandhi Bazaar arch, the gateway to one of the city's oldest market streets.",
                  "basavanagudi/01-arch.mp3"),
            _stop("Book Street", "Oldest bookshops in the city", "📚", 12.9448, 77.5705,
                  "Book Street is home to some of the oldest bookshops in the city. Step inside and browse.",
                  "basavanagudi/02-book-street.mp3"),
            _stop("Bull Temple", "Famous 16th-century temple", "🐂", 12.9419, 77.5680,
                  "The Bull Temple is famous for its monolithic Nandi, and gives the neighbourhood its name.",
                  "basavanagudi/03-bull-temple.mp3"),
            _stop("Bugle Rock Park", "Billion-year-old rock outcrop", "🌳", 12.9432, 77.5664,
                  "Bugle Rock is a rock outcrop that is around a billion years old, at the edge of the park.",
                  "basavanagudi/04-bugle-rock.mp3"),
        ],
    },
    {
        "name": "Cubbon Park Green Heart",
        "neighbourhood": "cubbon-park",
        "is_featured": True,
        "theme": "Nature", "difficulty": "Easy",
        "start_point": "Cubbon Park Bandstand Gate",
        "tags": ["Easy pace", "Accessibility info to be confirmed"],
        "includes": [t for t in INCLUDED if not t.startswith("Free cancellation")],
        "languages": ["English", "Kannada"], "gallery_images": [],
        "description": (
            "A free, easy stroll through Cubbon Park: the colonial bandstand gate, the State Library, trees over 150 "
            "years old and the Gothic-style High Court. Four stops over 1.5 km, at your own pace."
        ),
        "city": "Bangalore", "cover_image": None,
        "duration_min": 60, "distance_km": 1.5, "price_paise": 0, "is_free": True,
        "preview_audio_filename": "previews/cubbon-park.mp3",
        "preview_audio_title": "State Library",
        "preview_text": "Welcome to Cubbon Park. Here is a short introduction to the State Library.",
        "stops": [
            _stop("Bandstand Gate", "1880s colonial bandstand", "🎵", 12.9774, 77.5951,
                  "The colonial bandstand gate marks the start of our stroll through the park.",
                  "cubbon-park/01-bandstand.mp3"),
            _stop("State Library", "Built 1915, 100k volumes", "📚", 12.9788, 77.5940,
                  "The State Library was built in 1915 and holds around a hundred thousand volumes.",
                  "cubbon-park/02-library.mp3"),
            _stop("Heritage Trees", "Trees over 150 years old", "🌳", 12.9770, 77.5928,
                  "Look up. Some of the trees around you are more than a hundred and fifty years old.",
                  "cubbon-park/03-trees.mp3"),
            _stop("High Court", "Gothic-style, built 1867", "⚖️", 12.9795, 77.5908,
                  "Our walk ends at the Gothic-style High Court, completed in the late nineteenth century.",
                  "cubbon-park/04-high-court.mp3"),
        ],
    },
    {
        "name": "Colonial Cantonment Walk",
        "neighbourhood": "mg-road",
        "is_featured": True,
        "theme": "Colonial", "difficulty": "Moderate",
        "start_point": "MG Road Metro Exit 2",
        "tags": ["Moderate fitness", "Accessibility info to be confirmed"],
        "includes": INCLUDED, "languages": ["English", "Kannada"], "gallery_images": [],
        "description": (
            "Step out of MG Road Metro into colonial Bangalore: St. Mark's Cathedral, the Bowring Club and Windsor "
            "Manor, ending at the Cubbon Park gate. Five stops covering 2 km."
        ),
        "city": "Bangalore", "cover_image": None,
        "duration_min": 80, "distance_km": 2.0, "price_paise": 22900, "is_free": False,
        "preview_audio_filename": "previews/mg-road.mp3",
        "preview_audio_title": "St. Mark's Cathedral",
        "preview_text": "Welcome to the old cantonment. Next, the story of St. Mark's Cathedral.",
        "stops": [
            _stop("MG Road Metro", "Start point", "🚇", 12.9756, 77.6068,
                  "You have stepped out of MG Road Metro into what was once the colonial cantonment.",
                  "mg-road/01-metro.mp3"),
            _stop("St. Mark's Cathedral", "1812 — oldest church", "⛪", 12.9743, 77.6007,
                  "St. Mark's Cathedral dates from 1812 and is one of the oldest churches in the city.",
                  "mg-road/02-st-marks.mp3"),
            _stop("Bowring Club", "1868 — British social club", "🎳", 12.9722, 77.5997,
                  "The Bowring Club, founded in 1868, was the social heart of British Bangalore.",
                  "mg-road/03-bowring.mp3"),
            _stop("Windsor Manor", "1980s heritage hotel", "🏨", 12.9770, 77.5985,
                  "Windsor Manor is a heritage-style hotel from the nineteen eighties, built in a colonial manner.",
                  "mg-road/04-windsor.mp3"),
            _stop("Cubbon Park Gate", "End of walk", "🌿", 12.9755, 77.5960,
                  "Our walk ends at the gate of Cubbon Park. Thank you for walking with us.",
                  "mg-road/05-cubbon-gate.mp3"),
        ],
    },
]
