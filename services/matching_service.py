import numpy as np
from scipy.optimize import linear_sum_assignment
from database import get_db
from services.guest_service import get_guests_for_event, get_guest_answers, get_questions_for_event

# Category labels for "top shared values" display
CATEGORY_LABELS = {
    "personality": "Persönlichkeit",
    "values": "Werte",
    "lifestyle": "Lebensstil",
    "relationship": "Beziehung",
}


def compute_compatibility(answers_a: dict[int, int], answers_b: dict[int, int],
                          questions: list[dict]) -> tuple[float, list[str]]:
    """
    Compute compatibility score between two guests.
    Returns (score 0.0-1.0, list of top shared value categories).
    """
    total_weight = 0.0
    weighted_similarity = 0.0
    category_scores: dict[str, list[float]] = {}

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

    score = weighted_similarity / total_weight if total_weight > 0 else 0.0

    # Top shared values: categories with highest average similarity
    cat_avgs = {
        cat: sum(scores) / len(scores)
        for cat, scores in category_scores.items() if scores
    }
    top_cats = sorted(cat_avgs, key=cat_avgs.get, reverse=True)[:3]
    top_labels = [CATEGORY_LABELS.get(c, c) for c in top_cats]

    return score, top_labels


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


async def run_matching(event_id: str, event_type: str) -> list[dict]:
    """Run the matching algorithm for an event. Returns list of match dicts."""
    guests = await get_guests_for_event(event_id)
    # Only guests who completed the questionnaire
    guests = [g for g in guests if g["completed_questionnaire"]]

    if len(guests) < 2:
        return []

    questions = await get_questions_for_event(event_type)

    # Load all answers
    guest_answers = {}
    for g in guests:
        guest_answers[g["id"]] = await get_guest_answers(g["id"])

    n = len(guests)

    if event_type == "professional":
        return await _match_pool(
            guests, guest_answers, questions, event_id, "professional"
        )
    else:
        return await _match_romantic(
            guests, guest_answers, questions, event_id
        )


async def _match_pool(guests: list[dict], guest_answers: dict,
                      questions: list[dict], event_id: str,
                      match_type: str) -> list[dict]:
    """Match all guests in a single pool."""
    n = len(guests)
    compat_matrix = np.zeros((n, n))
    compat_details: dict[tuple[int, int], list[str]] = {}

    for i in range(n):
        for j in range(i + 1, n):
            score, top_vals = compute_compatibility(
                guest_answers[guests[i]["id"]],
                guest_answers[guests[j]["id"]],
                questions
            )
            compat_matrix[i][j] = score
            compat_matrix[j][i] = score
            compat_details[(i, j)] = top_vals
            compat_details[(j, i)] = top_vals

    cost_matrix = 1.0 - compat_matrix
    np.fill_diagonal(cost_matrix, 1e6)

    pairs = _solve_symmetric_assignment(n, cost_matrix, compat_matrix)

    matches = []
    for i, j, score in pairs:
        top_vals = compat_details.get((i, j), [])
        match = {
            "event_id": event_id,
            "guest_a_id": guests[i]["id"],
            "guest_a_name": guests[i]["name"],
            "guest_b_id": guests[j]["id"],
            "guest_b_name": guests[j]["name"],
            "compatibility_score": round(score, 3),
            "match_type": match_type,
            "top_shared_values": top_vals,
        }
        matches.append(match)

    return matches


async def _match_romantic(guests: list[dict], guest_answers: dict,
                          questions: list[dict], event_id: str) -> list[dict]:
    """Romantic matching with gender/attraction preferences."""
    n = len(guests)
    compat_matrix = np.zeros((n, n))
    compat_details: dict[tuple[int, int], list[str]] = {}

    # Only compute compatibility for romantically compatible pairs
    for i in range(n):
        for j in range(i + 1, n):
            if _are_romantically_compatible(guests[i], guests[j]):
                score, top_vals = compute_compatibility(
                    guest_answers[guests[i]["id"]],
                    guest_answers[guests[j]["id"]],
                    questions
                )
                compat_matrix[i][j] = score
                compat_matrix[j][i] = score
                compat_details[(i, j)] = top_vals
                compat_details[(j, i)] = top_vals

    cost_matrix = np.full((n, n), 1e6)
    for i in range(n):
        for j in range(i + 1, n):
            if compat_matrix[i][j] > 0:
                cost_matrix[i][j] = 1.0 - compat_matrix[i][j]
                cost_matrix[j][i] = 1.0 - compat_matrix[j][i]
    np.fill_diagonal(cost_matrix, 1e6)

    pairs = _solve_symmetric_assignment(n, cost_matrix, compat_matrix)

    matches = []
    matched_indices = set()
    for i, j, score in pairs:
        top_vals = compat_details.get((i, j), [])
        matches.append({
            "event_id": event_id,
            "guest_a_id": guests[i]["id"],
            "guest_a_name": guests[i]["name"],
            "guest_b_id": guests[j]["id"],
            "guest_b_name": guests[j]["name"],
            "compatibility_score": round(score, 3),
            "match_type": "romantic",
            "top_shared_values": top_vals,
        })
        matched_indices.add(i)
        matched_indices.add(j)

    # Unmatched guests get friendship matches among themselves
    unmatched = [i for i in range(n) if i not in matched_indices]
    if len(unmatched) >= 2:
        um_guests = [guests[i] for i in unmatched]
        um_answers = {guests[i]["id"]: guest_answers[guests[i]["id"]] for i in unmatched}
        friendship = await _match_pool(
            um_guests, um_answers, questions, event_id, "friendship"
        )
        matches.extend(friendship)

    return matches


async def save_matches(matches: list[dict]):
    """Persist matches to the database."""
    db = await get_db()
    try:
        for m in matches:
            await db.execute(
                "INSERT INTO matches (event_id, guest_a_id, guest_b_id, "
                "compatibility_score, match_type) VALUES (?, ?, ?, ?, ?)",
                (m["event_id"], m["guest_a_id"], m["guest_b_id"],
                 m["compatibility_score"], m["match_type"])
            )
        await db.commit()
    finally:
        await db.close()


async def get_match_for_guest(event_id: str, guest_id: str) -> dict | None:
    """Get a guest's match from the database."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT m.*, "
            "ga.name as guest_a_name, gb.name as guest_b_name "
            "FROM matches m "
            "JOIN guests ga ON m.guest_a_id = ga.id "
            "JOIN guests gb ON m.guest_b_id = gb.id "
            "WHERE m.event_id = ? AND (m.guest_a_id = ? OR m.guest_b_id = ?)",
            (event_id, guest_id, guest_id)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        row = dict(row)
        # Return the OTHER person's name
        if row["guest_a_id"] == guest_id:
            return {
                "name": row["guest_b_name"],
                "compatibility_score": row["compatibility_score"],
                "match_type": row["match_type"],
            }
        else:
            return {
                "name": row["guest_a_name"],
                "compatibility_score": row["compatibility_score"],
                "match_type": row["match_type"],
            }
    finally:
        await db.close()
