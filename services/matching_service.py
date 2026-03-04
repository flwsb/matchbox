import json
import numpy as np
from scipy.optimize import linear_sum_assignment
from database import get_db
from services.guest_service import get_guests_for_event, get_guest_answers, get_questions_for_event

# Category labels for display
CATEGORY_LABELS = {
    "personality": "Persönlichkeit",
    "values": "Werte",
    "lifestyle": "Lebensstil",
    "relationship": "Beziehung",
}

# Clue templates by category (vague)
CLUE_TEMPLATES_VAGUE = {
    "personality": "Dein Match hat eine ähnliche Persönlichkeit wie du.",
    "values": "Dein Match teilt wichtige Werte mit dir.",
    "lifestyle": "Dein Match führt einen ähnlichen Lebensstil wie du.",
    "relationship": "Dein Match hat ähnliche Beziehungsvorstellungen wie du.",
}

# Clue templates derived from question keywords
CLUE_QUESTION_MAP = [
    ("ehrlich", "Dein Match schätzt Ehrlichkeit über alles."),
    ("Mittelpunkt", "Dein Match ist gerne unter Menschen."),
    ("ruhig und gelassen", "Dein Match bleibt auch unter Druck ruhig."),
    ("Kompromisse", "Dein Match ist kompromissbereit."),
    ("Erfolg und Ehrgeiz", "Dein Match ist ambitioniert und ehrgeizig."),
    ("zweite Chancen", "Dein Match glaubt an zweite Chancen."),
    ("Traditionen", "Dein Match schätzt Traditionen und Wurzeln."),
    ("Freiheit", "Dein Match liebt die persönliche Freiheit."),
    ("tiefgründige", "Dein Match bevorzugt tiefgründige Gespräche."),
    ("zuhause", "Dein Match ist eher ein gemütlicher Typ."),
    ("Körperliche Nähe", "Dein Match schätzt körperliche Nähe."),
    ("intellektuell", "Dein Match liebt intellektuelle Herausforderungen."),
    ("alleine", "Dein Match arbeitet gerne selbstständig."),
    ("Mentoring", "Dein Match hilft gerne anderen bei ihrer Entwicklung."),
]


def compute_compatibility(answers_a: dict[int, int], answers_b: dict[int, int],
                          questions: list[dict]) -> tuple[float, list[str], dict]:
    """
    Compute compatibility score between two guests.
    Returns (score 0.0-1.0, top shared value labels, insights dict).
    """
    total_weight = 0.0
    weighted_similarity = 0.0
    category_scores: dict[str, list[float]] = {}
    question_alignments: list[dict] = []

    for q in questions:
        qid = q["id"]
        a_val = answers_a.get(qid)
        b_val = answers_b.get(qid)
        if a_val is None or b_val is None:
            continue

        # Normalize to 0-1
        a_norm = (a_val - 1) / 4.0
        b_norm = (b_val - 1) / 4.0

        if q["reverse_scored"]:
            a_norm = 1.0 - a_norm
            b_norm = 1.0 - b_norm

        similarity = 1.0 - abs(a_norm - b_norm)

        # Conviction bonus/penalty for values and relationship questions
        if q["category"] in ("values", "relationship"):
            a_conv = abs(a_norm - 0.5) * 2
            b_conv = abs(b_norm - 0.5) * 2
            same_side = (a_norm - 0.5) * (b_norm - 0.5) > 0

            if same_side:
                similarity = min(1.0, similarity + a_conv * b_conv * 0.3)
            else:
                similarity = max(0.0, similarity - a_conv * b_conv * 0.2)

        weight = q["weight"]
        weighted_similarity += similarity * weight
        total_weight += weight

        cat = q["category"]
        if cat not in category_scores:
            category_scores[cat] = []
        category_scores[cat].append(similarity)

        question_alignments.append({
            "question_text": q["text_de"],
            "category": cat,
            "similarity": round(similarity, 3),
        })

    score = weighted_similarity / total_weight if total_weight > 0 else 0.0

    # Top shared values: categories with highest average similarity
    cat_avgs = {
        cat: sum(scores) / len(scores)
        for cat, scores in category_scores.items() if scores
    }
    top_cats = sorted(cat_avgs, key=cat_avgs.get, reverse=True)[:3]
    top_labels = [CATEGORY_LABELS.get(c, c) for c in top_cats]

    # Build insights
    question_alignments.sort(key=lambda x: x["similarity"], reverse=True)
    top_questions = question_alignments[:3]

    insight_sentences = []
    for qa in top_questions:
        label = CATEGORY_LABELS.get(qa["category"], qa["category"])
        # Truncate question text for readability
        q_short = qa["question_text"][:60].rstrip(".")
        insight_sentences.append(f"Ihr seid euch einig: \"{q_short}\"")

    insights = {
        "category_scores": {
            cat: {"score": round(avg, 3), "label": CATEGORY_LABELS.get(cat, cat)}
            for cat, avg in cat_avgs.items()
        },
        "top_question_alignments": top_questions,
        "insight_sentences": insight_sentences,
    }

    return score, top_labels, insights


def _are_romantically_compatible(guest_a: dict, guest_b: dict) -> bool:
    a_attracted = guest_a.get("attracted_to")
    b_attracted = guest_b.get("attracted_to")
    a_gender = guest_a.get("gender")
    b_gender = guest_b.get("gender")

    if not a_attracted or not b_attracted or not a_gender or not b_gender:
        return False

    a_likes_b = (a_attracted == "everyone" or a_attracted == b_gender)
    b_likes_a = (b_attracted == "everyone" or b_attracted == a_gender)

    return a_likes_b and b_likes_a


def _solve_symmetric_assignment(n: int, cost_matrix: np.ndarray,
                                compat_matrix: np.ndarray) -> list[tuple[int, int, float]]:
    """Solve symmetric matching using duplication trick."""
    if n < 2:
        return []

    INF = 1e6
    big = np.full((2 * n, 2 * n), INF)
    big[:n, n:] = cost_matrix
    big[n:, :n] = cost_matrix

    row_ind, col_ind = linear_sum_assignment(big)

    pairs = set()
    for r, c in zip(row_ind, col_ind):
        if big[r][c] >= INF:
            continue
        orig_r = r if r < n else r - n
        orig_c = c if c < n else c - n
        if orig_r != orig_c:
            pair = (min(orig_r, orig_c), max(orig_r, orig_c))
            pairs.add(pair)

    return [
        (i, j, compat_matrix[i][j])
        for i, j in pairs
    ]


async def get_previous_pairs(event_id: str) -> set[frozenset[str]]:
    """Load all existing match pairs for an event (across all rounds)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT guest_a_id, guest_b_id FROM matches WHERE event_id = ?",
            (event_id,)
        )
        rows = await cursor.fetchall()
        return {frozenset([r["guest_a_id"], r["guest_b_id"]]) for r in rows}
    finally:
        await db.close()


async def run_matching(event_id: str, event_type: str,
                       round_number: int = 1) -> list[dict]:
    """Run the matching algorithm for an event. Returns list of match dicts."""
    event_db = await _get_event_for_matching(event_id)
    guests = await get_guests_for_event(event_id)
    # Only guests who completed the questionnaire
    guests = [g for g in guests if g["completed_questionnaire"]]

    # Age filter
    if event_db:
        min_age = event_db.get("min_age")
        max_age = event_db.get("max_age")
        if min_age is not None or max_age is not None:
            guests = [
                g for g in guests
                if g.get("age") is not None
                and (min_age is None or g["age"] >= min_age)
                and (max_age is None or g["age"] <= max_age)
            ]

    if len(guests) < 2:
        return []

    questions = await get_questions_for_event(event_type)

    # Load all answers
    guest_answers = {}
    for g in guests:
        guest_answers[g["id"]] = await get_guest_answers(g["id"])

    # Load previous pairs to exclude in multi-round
    previous_pairs = await get_previous_pairs(event_id) if round_number > 1 else set()

    if event_type == "professional":
        return await _match_pool(
            guests, guest_answers, questions, event_id, "professional",
            previous_pairs=previous_pairs
        )
    else:
        return await _match_romantic(
            guests, guest_answers, questions, event_id,
            previous_pairs=previous_pairs
        )


async def _get_event_for_matching(event_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def _match_pool(guests: list[dict], guest_answers: dict,
                      questions: list[dict], event_id: str,
                      match_type: str,
                      previous_pairs: set[frozenset[str]] | None = None) -> list[dict]:
    """Match all guests in a single pool."""
    n = len(guests)
    compat_matrix = np.zeros((n, n))
    compat_details: dict[tuple[int, int], tuple[list[str], dict]] = {}

    for i in range(n):
        for j in range(i + 1, n):
            score, top_vals, insights = compute_compatibility(
                guest_answers[guests[i]["id"]],
                guest_answers[guests[j]["id"]],
                questions
            )
            compat_matrix[i][j] = score
            compat_matrix[j][i] = score
            compat_details[(i, j)] = (top_vals, insights)
            compat_details[(j, i)] = (top_vals, insights)

    cost_matrix = 1.0 - compat_matrix
    np.fill_diagonal(cost_matrix, 1e6)

    # Exclude previous pairs
    if previous_pairs:
        for i in range(n):
            for j in range(i + 1, n):
                pair = frozenset([guests[i]["id"], guests[j]["id"]])
                if pair in previous_pairs:
                    cost_matrix[i][j] = 1e6
                    cost_matrix[j][i] = 1e6

    pairs = _solve_symmetric_assignment(n, cost_matrix, compat_matrix)

    matches = []
    for i, j, score in pairs:
        top_vals, insights = compat_details.get((i, j), ([], {}))
        match = {
            "event_id": event_id,
            "guest_a_id": guests[i]["id"],
            "guest_a_name": guests[i]["name"],
            "guest_b_id": guests[j]["id"],
            "guest_b_name": guests[j]["name"],
            "compatibility_score": round(score, 3),
            "match_type": match_type,
            "top_shared_values": top_vals,
            "insights": insights,
        }
        matches.append(match)

    return matches


async def _match_romantic(guests: list[dict], guest_answers: dict,
                          questions: list[dict], event_id: str,
                          previous_pairs: set[frozenset[str]] | None = None) -> list[dict]:
    """Romantic matching with gender/attraction preferences."""
    n = len(guests)
    compat_matrix = np.zeros((n, n))
    compat_details: dict[tuple[int, int], tuple[list[str], dict]] = {}

    # Only compute compatibility for romantically compatible pairs
    for i in range(n):
        for j in range(i + 1, n):
            if _are_romantically_compatible(guests[i], guests[j]):
                score, top_vals, insights = compute_compatibility(
                    guest_answers[guests[i]["id"]],
                    guest_answers[guests[j]["id"]],
                    questions
                )
                compat_matrix[i][j] = score
                compat_matrix[j][i] = score
                compat_details[(i, j)] = (top_vals, insights)
                compat_details[(j, i)] = (top_vals, insights)

    cost_matrix = np.full((n, n), 1e6)
    for i in range(n):
        for j in range(i + 1, n):
            if compat_matrix[i][j] > 0:
                cost_matrix[i][j] = 1.0 - compat_matrix[i][j]
                cost_matrix[j][i] = 1.0 - compat_matrix[j][i]
    np.fill_diagonal(cost_matrix, 1e6)

    # Exclude previous pairs
    if previous_pairs:
        for i in range(n):
            for j in range(i + 1, n):
                pair = frozenset([guests[i]["id"], guests[j]["id"]])
                if pair in previous_pairs:
                    cost_matrix[i][j] = 1e6
                    cost_matrix[j][i] = 1e6

    pairs = _solve_symmetric_assignment(n, cost_matrix, compat_matrix)

    matches = []
    matched_indices = set()
    for i, j, score in pairs:
        top_vals, insights = compat_details.get((i, j), ([], {}))
        matches.append({
            "event_id": event_id,
            "guest_a_id": guests[i]["id"],
            "guest_a_name": guests[i]["name"],
            "guest_b_id": guests[j]["id"],
            "guest_b_name": guests[j]["name"],
            "compatibility_score": round(score, 3),
            "match_type": "romantic",
            "top_shared_values": top_vals,
            "insights": insights,
        })
        matched_indices.add(i)
        matched_indices.add(j)

    # Unmatched guests get friendship matches among themselves
    unmatched = [i for i in range(n) if i not in matched_indices]
    if len(unmatched) >= 2:
        um_guests = [guests[i] for i in unmatched]
        um_answers = {guests[i]["id"]: guest_answers[guests[i]["id"]] for i in unmatched}
        friendship = await _match_pool(
            um_guests, um_answers, questions, event_id, "friendship",
            previous_pairs=previous_pairs
        )
        matches.extend(friendship)

    return matches


async def save_matches(matches: list[dict], round_number: int = 1):
    """Persist matches to the database."""
    db = await get_db()
    try:
        for m in matches:
            insights_str = json.dumps(m.get("insights", {}), ensure_ascii=False)
            await db.execute(
                "INSERT INTO matches (event_id, guest_a_id, guest_b_id, "
                "compatibility_score, match_type, round, insights_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (m["event_id"], m["guest_a_id"], m["guest_b_id"],
                 m["compatibility_score"], m["match_type"], round_number,
                 insights_str)
            )
        await db.commit()
    finally:
        await db.close()


async def get_match_for_guest(event_id: str, guest_id: str,
                              round_number: int | None = None) -> dict | None:
    """Get a guest's match. If round_number is None, returns latest round."""
    db = await get_db()
    try:
        if round_number is not None:
            cursor = await db.execute(
                "SELECT m.*, ga.name as guest_a_name, gb.name as guest_b_name "
                "FROM matches m "
                "JOIN guests ga ON m.guest_a_id = ga.id "
                "JOIN guests gb ON m.guest_b_id = gb.id "
                "WHERE m.event_id = ? AND (m.guest_a_id = ? OR m.guest_b_id = ?) "
                "AND m.round = ?",
                (event_id, guest_id, guest_id, round_number)
            )
        else:
            cursor = await db.execute(
                "SELECT m.*, ga.name as guest_a_name, gb.name as guest_b_name "
                "FROM matches m "
                "JOIN guests ga ON m.guest_a_id = ga.id "
                "JOIN guests gb ON m.guest_b_id = gb.id "
                "WHERE m.event_id = ? AND (m.guest_a_id = ? OR m.guest_b_id = ?) "
                "ORDER BY m.round DESC LIMIT 1",
                (event_id, guest_id, guest_id)
            )
        row = await cursor.fetchone()
        if row is None:
            return None
        row = dict(row)

        insights = {}
        if row.get("insights_json"):
            try:
                insights = json.loads(row["insights_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        if row["guest_a_id"] == guest_id:
            return {
                "name": row["guest_b_name"],
                "compatibility_score": row["compatibility_score"],
                "match_type": row["match_type"],
                "top_shared_values": list(insights.get("category_scores", {}).keys())[:3],
                "insights": insights,
                "round": row["round"],
            }
        else:
            return {
                "name": row["guest_a_name"],
                "compatibility_score": row["compatibility_score"],
                "match_type": row["match_type"],
                "top_shared_values": list(insights.get("category_scores", {}).keys())[:3],
                "insights": insights,
                "round": row["round"],
            }
    finally:
        await db.close()


async def get_all_matches_for_guest(event_id: str, guest_id: str) -> list[dict]:
    """Get all matches across all rounds for a guest."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT m.*, ga.name as guest_a_name, gb.name as guest_b_name "
            "FROM matches m "
            "JOIN guests ga ON m.guest_a_id = ga.id "
            "JOIN guests gb ON m.guest_b_id = gb.id "
            "WHERE m.event_id = ? AND (m.guest_a_id = ? OR m.guest_b_id = ?) "
            "ORDER BY m.round ASC",
            (event_id, guest_id, guest_id)
        )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            row = dict(row)
            insights = {}
            if row.get("insights_json"):
                try:
                    insights = json.loads(row["insights_json"])
                except (json.JSONDecodeError, TypeError):
                    pass

            if row["guest_a_id"] == guest_id:
                name = row["guest_b_name"]
            else:
                name = row["guest_a_name"]

            result.append({
                "name": name,
                "compatibility_score": row["compatibility_score"],
                "match_type": row["match_type"],
                "insights": insights,
                "round": row["round"],
            })
        return result
    finally:
        await db.close()


async def get_matches_for_round(event_id: str, round_number: int) -> list[dict]:
    """Get all matches for a specific round (with guest names and insights)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT m.*, ga.name as guest_a_name, gb.name as guest_b_name "
            "FROM matches m "
            "JOIN guests ga ON m.guest_a_id = ga.id "
            "JOIN guests gb ON m.guest_b_id = gb.id "
            "WHERE m.event_id = ? AND m.round = ?",
            (event_id, round_number)
        )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            row = dict(row)
            insights = {}
            if row.get("insights_json"):
                try:
                    insights = json.loads(row["insights_json"])
                except (json.JSONDecodeError, TypeError):
                    pass
            row["insights"] = insights
            result.append(row)
        return result
    finally:
        await db.close()


async def get_all_event_matches(event_id: str) -> list[dict]:
    """Get all matches for an event across all rounds."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT m.*, ga.name as guest_a_name, gb.name as guest_b_name "
            "FROM matches m "
            "JOIN guests ga ON m.guest_a_id = ga.id "
            "JOIN guests gb ON m.guest_b_id = gb.id "
            "WHERE m.event_id = ? ORDER BY m.round, m.compatibility_score DESC",
            (event_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


def generate_clue_for_guest(match_row: dict, for_side: str, clue_number: int) -> str:
    """
    Generate a clue about one guest for the other.
    for_side: 'a' means generate clue about guest_b for guest_a, and vice versa.
    clue_number: 1 (vague), 2 (medium), 3 (specific).
    """
    insights = match_row.get("insights", {})
    cat_scores = insights.get("category_scores", {})
    top_questions = insights.get("top_question_alignments", [])

    if clue_number == 1:
        # Vague: best category
        if cat_scores:
            best_cat = max(cat_scores, key=lambda c: cat_scores[c].get("score", 0))
            return CLUE_TEMPLATES_VAGUE.get(best_cat,
                "Dein Match hat viel mit dir gemeinsam.")
        return "Dein Match hat viel mit dir gemeinsam."

    # Medium / specific: question-based clues
    q_idx = clue_number - 2  # 0 for clue 2, 1 for clue 3
    if q_idx < len(top_questions):
        q_text = top_questions[q_idx].get("question_text", "")
        for keyword, clue_text in CLUE_QUESTION_MAP:
            if keyword.lower() in q_text.lower():
                return clue_text

    # Fallback
    fallbacks = [
        "Dein Match hat einen ähnlichen Blick auf die Welt.",
        "Dein Match überrascht dich vielleicht - halte die Augen offen!",
    ]
    return fallbacks[min(q_idx, len(fallbacks) - 1)]
