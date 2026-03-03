"""Seed the questions table with the 12 science-based questions (German)."""
import asyncio
from database import init_db, get_db

QUESTIONS = [
    # Personality (both)
    {
        "text_de": "Ich bin lieber ehrlich und unbeliebt als unehrlich und beliebt.",
        "category": "personality",
        "event_type": "both",
        "weight": 1.5,
        "reverse_scored": 0,
    },
    {
        "text_de": "Ich stehe gerne im Mittelpunkt bei sozialen Anlässen.",
        "category": "personality",
        "event_type": "both",
        "weight": 1.0,
        "reverse_scored": 0,
    },
    {
        "text_de": "Ich bleibe auch unter Druck ruhig und gelassen.",
        "category": "personality",
        "event_type": "both",
        "weight": 1.0,
        "reverse_scored": 1,
    },
    {
        "text_de": "Ich bin bereit Kompromisse einzugehen, auch wenn ich überzeugt bin, Recht zu haben.",
        "category": "personality",
        "event_type": "both",
        "weight": 1.2,
        "reverse_scored": 0,
    },
    # Values (both)
    {
        "text_de": "Beruflicher Erfolg und Ehrgeiz gehören zu den wichtigsten Dingen im Leben.",
        "category": "values",
        "event_type": "both",
        "weight": 1.5,
        "reverse_scored": 0,
    },
    {
        "text_de": "Ich glaube daran, Menschen zweite Chancen zu geben, auch wenn sie schwere Fehler gemacht haben.",
        "category": "values",
        "event_type": "both",
        "weight": 1.3,
        "reverse_scored": 0,
    },
    {
        "text_de": "Traditionen und kulturelle Wurzeln sind mir wichtig.",
        "category": "values",
        "event_type": "both",
        "weight": 1.2,
        "reverse_scored": 0,
    },
    {
        "text_de": "Persönliche Freiheit ist mir wichtiger als Sicherheit und Stabilität.",
        "category": "values",
        "event_type": "both",
        "weight": 1.3,
        "reverse_scored": 0,
    },
    # Lifestyle (both)
    {
        "text_de": "Ich bevorzuge tiefgründige Gespräche gegenüber Small Talk.",
        "category": "lifestyle",
        "event_type": "both",
        "weight": 1.0,
        "reverse_scored": 0,
    },
    {
        "text_de": "Ich verbringe einen Samstagabend lieber zuhause als auf einer Party.",
        "category": "lifestyle",
        "event_type": "both",
        "weight": 0.8,
        "reverse_scored": 0,
    },
    # Relationship/Connection — romantic versions
    {
        "text_de": "Körperliche Nähe ist mir wichtig, um mich geliebt zu fühlen.",
        "category": "relationship",
        "event_type": "romantic",
        "weight": 1.0,
        "reverse_scored": 0,
    },
    {
        "text_de": "Ich brauche jemanden, der mich intellektuell herausfordert.",
        "category": "relationship",
        "event_type": "romantic",
        "weight": 1.0,
        "reverse_scored": 0,
    },
    # Relationship/Connection — professional versions
    {
        "text_de": "Ich arbeite lieber alleine als im Team.",
        "category": "relationship",
        "event_type": "professional",
        "weight": 1.0,
        "reverse_scored": 0,
    },
    {
        "text_de": "Ich schätze Mentoring und helfe gerne anderen bei ihrer Entwicklung.",
        "category": "relationship",
        "event_type": "professional",
        "weight": 1.0,
        "reverse_scored": 0,
    },
]


async def seed():
    await init_db()
    db = await get_db()
    try:
        # Check if questions already exist
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM questions")
        row = await cursor.fetchone()
        if row["cnt"] > 0:
            print(f"Fragen existieren bereits ({row['cnt']} Stück). Überspringe Seed.")
            return

        for q in QUESTIONS:
            await db.execute(
                "INSERT INTO questions (text_de, category, event_type, weight, reverse_scored) "
                "VALUES (?, ?, ?, ?, ?)",
                (q["text_de"], q["category"], q["event_type"], q["weight"], q["reverse_scored"])
            )
        await db.commit()
        print(f"{len(QUESTIONS)} Fragen erfolgreich eingefügt.")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(seed())
