"""Shared demo tour data used by both app.seed and the placeholder audio generator."""

NEIGHBOURHOODS = [
    {
        "name": "Malleshwaram",
        "slug": "malleshwaram",
        "description": "One of Bangalore's oldest planned extensions: temple lanes, a bustling 8th Cross market and century-old bungalows.",
        "centroid_lat": 13.0035,
        "centroid_lng": 77.5647,
    },
    {
        "name": "Basavanagudi",
        "slug": "basavanagudi",
        "description": "A storied south-side neighbourhood of ancient rock formations, the Bull Temple and leafy parks.",
        "centroid_lat": 12.9425,
        "centroid_lng": 77.5748,
    },
    {
        "name": "Cubbon Park",
        "slug": "cubbon-park",
        "description": "The city's green lung, ringed by Victorian-era landmarks in the heart of Bangalore.",
        "centroid_lat": 12.9763,
        "centroid_lng": 77.5929,
    },
]

TOURS = [
    {
        "name": "Malleshwaram Morning Market Walk",
        "neighbourhood": "malleshwaram",
        "description": (
            "A ~2km walk through Malleshwaram's flower and vegetable markets, "
            "temple lanes, and century-old bungalows, tracing how one of "
            "Bangalore's oldest planned extensions grew up around its 8th Cross market."
        ),
        "city": "Bangalore",
        "cover_image": "https://images.unsplash.com/photo-1596484552834-6a58f850e0a1",
        "duration_min": 45,
        "distance_km": 2.0,
        "price_paise": 19900,
        "is_free": False,
        "stops": [
            {
                "name": "Malleshwaram Circle",
                "narrative_text": "Start at the circle — once the edge of the original 1889 plague-relocation extension.",
                "lat": 13.0035, "lng": 77.5647, "trigger_radius_m": 30,
                "audio_filename": "malleshwaram/01-circle.mp3",
            },
            {
                "name": "8th Cross Market",
                "narrative_text": "The flower and vegetable market that gives the neighbourhood its rhythm every morning.",
                "lat": 13.0043, "lng": 77.5701, "trigger_radius_m": 30,
                "audio_filename": "malleshwaram/02-market.mp3",
            },
            {
                "name": "Kadu Malleshwara Temple",
                "narrative_text": "The temple the neighbourhood is named after — older than the planned extension around it.",
                "lat": 13.0071, "lng": 77.5665, "trigger_radius_m": 25,
                "audio_filename": "malleshwaram/03-temple.mp3",
            },
        ],
    },
    {
        "name": "Basavanagudi Heritage Trail",
        "neighbourhood": "basavanagudi",
        "description": (
            "Wander past Bull Temple, Bugle Rock, and the old Basavanagudi "
            "bungalows on a walk through one of the city's most storied south-side neighbourhoods."
        ),
        "city": "Bangalore",
        "cover_image": "https://images.unsplash.com/photo-1602216056096-3b40cc0c7728",
        "duration_min": 60,
        "distance_km": 2.6,
        "price_paise": 24900,
        "is_free": False,
        "stops": [
            {
                "name": "Bugle Rock Park",
                "narrative_text": "A 3-billion-year-old rock outcrop and one of the oldest geological formations in the city.",
                "lat": 12.9432, "lng": 77.5715, "trigger_radius_m": 35,
                "audio_filename": "basavanagudi/01-bugle-rock.mp3",
            },
            {
                "name": "Bull Temple",
                "narrative_text": "Home to one of the largest monolithic Nandi statues in India, carved from a single boulder.",
                "lat": 12.9425, "lng": 77.5719, "trigger_radius_m": 30,
                "audio_filename": "basavanagudi/02-bull-temple.mp3",
            },
        ],
    },
    {
        "name": "Cubbon Park Free Sampler Walk",
        "neighbourhood": "cubbon-park",
        "description": "A short free taster walk through Cubbon Park to try the app before buying a full tour.",
        "city": "Bangalore",
        "cover_image": "https://images.unsplash.com/photo-1585129918465-045a1e0d858b",
        "duration_min": 20,
        "distance_km": 1.0,
        "price_paise": 0,
        "is_free": True,
        "stops": [
            {
                "name": "Cubbon Park Bandstand",
                "narrative_text": "Built in 1927, this Victorian bandstand is one of the park's most recognisable landmarks.",
                "lat": 12.9762, "lng": 77.5929, "trigger_radius_m": 30,
                "audio_filename": "cubbon/01-bandstand.mp3",
            },
        ],
    },
]
