"""Seven case themes. One typography / spacing / component system; seven palettes (see static/css/mystiq.css)."""
THEMES = {
    1: dict(slug="emerald-noir", name="Emerald Noir", swatches=["#0b2a1f", "#2fbf8a", "#b99a4d", "#f1ecd9"],
            palette="Forest green · Emerald · Antique brass · Ivory", motif="Jewel theft, private estate, secret keys.",
            focus="Observation vs assumption", instrument="stance"),
    2: dict(slug="midnight-correspondence", name="Midnight Correspondence", swatches=["#0b1230", "#07080f", "#c3cada", "#8e3a52"],
            palette="Midnight blue · Ink black · Silver · Muted burgundy", motif="Secret letters, hidden messages, information leakage.",
            focus="Information leakage", instrument="leakage"),
    3: dict(slug="gothic-archive", name="Gothic Archive", swatches=["#3a1210", "#4a2118", "#e8a33d", "#f1e4c7"],
            palette="Burgundy · Mahogany · Candle amber · Cream", motif="Old library, clocks, historical records.",
            focus="Timelines & false contradictions", instrument="time"),
    4: dict(slug="railway-mystery", name="Railway Mystery", swatches=["#2f7a55", "#c9a24a", "#8d9690", "#e04a3a"],
            palette="Railway green · Brass · Smoke grey · Signal red", motif="Train compartments, passenger descriptions, identities.",
            focus="Reference resolution", instrument="coref"),
    5: dict(slug="clockwork-noir", name="Clockwork Noir", swatches=["#17181a", "#d2793f", "#2aa6a0", "#f1eadb"],
            palette="Charcoal · Copper · Teal · Warm ivory", motif="Mechanical clocks, gears, hidden second keys.",
            focus="Literally true but misleading", instrument="nli"),
    6: dict(slug="poisoned-elegance", name="Poisoned Elegance", swatches=["#2b1535", "#a3203f", "#e6cfa0", "#cfcfd8"],
            palette="Deep plum · Wine red · Champagne · Silver", motif="Aristocratic dinner, invitations, seating plans.",
            focus="Entities across documents", instrument="ner"),
    7: dict(slug="the-last-conspiracy", name="The Last Conspiracy", swatches=["#16161a", "#c8283a", "#b5b6bd", "#e2c777"],
            palette="Charcoal · Crimson · Antique silver · Pale gold", motif="Final investigation, deception, interconnected evidence.",
            focus="Three independent proofs", instrument="retrieval"),
}
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII"}
DOC_KIND = {"letter": "letter", "note": "note", "record": "record", "report": "report", "schedule": "schedule", "statement": "statement",
            "diary": "diary", "newspaper": "newspaper", "plan": "plan", "register": "register", "telegram": "telegram", "receipt": "receipt"}
