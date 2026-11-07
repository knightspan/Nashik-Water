"""Seed the 7 Nashik monitoring sites.

Coordinates are approximate placeholders; edit them from the admin panel.
Only Ramkund has a real sensor node — the other six are simulated.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SITES: list[dict[str, object]] = [
    {
        "id": "ugamsthan",
        "name_en": "Ugamsthan, Trimbakeshwar (origin of Godavari)",
        "name_mr": "उगमस्थान, त्र्यंबकेश्वर",
        "kind": "spring",
        "lat": 19.9236,
        "lon": 73.5186,
        "simulated": True,
        "description_en": (
            "Origin of the Godavari on the Brahmagiri hills above Trimbakeshwar. "
            "Upstream reference site: water here is expected to be the cleanest in the network."
        ),
        "description_mr": (
            "त्र्यंबकेश्वरच्या ब्रह्मगिरी डोंगरावरील गोदावरीचे उगमस्थान. "
            "हे संदर्भ ठिकाण असून येथील पाणी सर्वात स्वच्छ असणे अपेक्षित आहे."
        ),
    },
    {
        "id": "kushavart",
        "name_en": "Kushavart Kund, Trimbakeshwar",
        "name_mr": "कुशावर्त कुंड, त्र्यंबकेश्वर",
        "kind": "kund",
        "lat": 19.9327,
        "lon": 73.5306,
        "simulated": True,
        "description_en": (
            "Sacred bathing tank in Trimbakeshwar town. "
            "Many pilgrims bathe here in the morning, which briefly raises turbidity."
        ),
        "description_mr": (
            "त्र्यंबकेश्वर गावातील पवित्र स्नानकुंड. "
            "सकाळी अनेक भाविक येथे स्नान करतात, त्यामुळे काही वेळ गढूळपणा वाढतो."
        ),
    },
    {
        "id": "gangapur_dam",
        "name_en": "Gangapur Dam",
        "name_mr": "गंगापूर धरण",
        "kind": "reservoir",
        "lat": 20.0400,
        "lon": 73.6700,
        "simulated": True,
        "description_en": (
            "Reservoir on the Godavari that supplies most of Nashik city's raw drinking water "
            "(it is treated before supply)."
        ),
        "description_mr": (
            "गोदावरीवरील धरण, जे नाशिक शहराला बहुतेक कच्चे पिण्याचे पाणी पुरवते "
            "(पुरवठ्यापूर्वी त्यावर प्रक्रिया केली जाते)."
        ),
    },
    {
        "id": "someshwar",
        "name_en": "Godavari at Someshwar",
        "name_mr": "सोमेश्वर",
        "kind": "river",
        "lat": 20.0236,
        "lon": 73.7383,
        "simulated": True,
        "description_en": (
            "The Godavari below Gangapur Dam near the Someshwar temple and waterfall, "
            "at the western edge of the city."
        ),
        "description_mr": (
            "शहराच्या पश्चिम टोकाला, सोमेश्वर मंदिर आणि धबधब्याजवळ, " "गंगापूर धरणाखालील गोदावरी नदी."
        ),
    },
    {
        "id": "ramkund",
        "name_en": "Ramkund (Godavari ghats)",
        "name_mr": "रामकुंड",
        "kind": "river",
        "lat": 20.0074,
        "lon": 73.7924,
        "simulated": False,
        "description_en": (
            "Main bathing ghat on the Godavari in Panchavati. "
            "This is the only site with a real sensor node, so its data is LIVE."
        ),
        "description_mr": (
            "पंचवटीतील गोदावरीवरील मुख्य स्नानघाट. "
            "येथे प्रत्यक्ष सेन्सर नोड बसवलेला असल्याने येथील माहिती थेट (LIVE) आहे."
        ),
    },
    {
        "id": "tapovan",
        "name_en": "Tapovan (Godavari)",
        "name_mr": "तपोवन",
        "kind": "river",
        "lat": 20.0035,
        "lon": 73.8135,
        "simulated": True,
        "description_en": (
            "The Godavari at Tapovan, downstream of the ghats, "
            "after the river has passed through the city centre."
        ),
        "description_mr": (
            "शहराच्या मध्यभागातून वाहत आल्यानंतर, घाटांच्या खालच्या बाजूस " "तपोवन येथील गोदावरी नदी."
        ),
    },
    {
        "id": "nandini",
        "name_en": "Nandini (Nasardi) river",
        "name_mr": "नंदिनी (नासर्डी) नदी",
        "kind": "urban river",
        "lat": 19.9900,
        "lon": 73.7700,
        "simulated": True,
        "description_en": (
            "Urban tributary of the Godavari that receives storm-water and drainage "
            "from city areas."
        ),
        "description_mr": (
            "गोदावरीची शहरी उपनदी, जिच्यात शहरातील पावसाचे पाणी आणि नाल्यांचे पाणी मिसळते."
        ),
    },
]


def upgrade() -> None:
    sites = sa.table(
        "sites",
        sa.column("id", sa.String),
        sa.column("name_en", sa.String),
        sa.column("name_mr", sa.String),
        sa.column("kind", sa.String),
        sa.column("lat", sa.Float),
        sa.column("lon", sa.Float),
        sa.column("simulated", sa.Boolean),
        sa.column("active", sa.Boolean),
        sa.column("description_en", sa.Text),
        sa.column("description_mr", sa.Text),
    )
    op.bulk_insert(sites, [{**s, "active": True} for s in SITES])


def downgrade() -> None:
    ids = ", ".join("'" + str(s["id"]) + "'" for s in SITES)
    op.execute(f"DELETE FROM sites WHERE id IN ({ids})")
