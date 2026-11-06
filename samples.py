"""Demo inputs. All companies, tickers and events are fictional."""

HEADLINES = """NWE: Northwind Energy beats quarterly earnings estimates on strong gas prices
NWE: Northwind Energy delays offshore wind project by 18 months
CLRB: Clearbrook Bank raises full-year net interest income guidance
CLRB: Clearbrook Bank faces regulator review of its loan-loss provisioning
VTX: Vertex Logistics announces 8% workforce reduction amid weak demand
VTX: Vertex Logistics completes acquisition of regional freight operator
Central bank holds rates steady, signals cuts later in the year"""

SNIPPETS = """Harbourline Trading fined €4.2m for failures in its anti-money laundering controls
Meridian Metals denies reports that it shipped dual-use goods to a sanctioned buyer
Oakridge Foods opens new distribution centre in Cork, creating 120 jobs
Former CFO of Brightwater Capital charged with falsifying accounts
Silverline Payments partners with a fintech to launch instant cross-border transfers
Prosecutors investigate alleged bribes paid by Castellan Construction to win public contracts"""

TRANSCRIPT = """Operator: Good morning and welcome to Clearbrook Bank's third-quarter 2026 earnings call.

CEO: Thank you. Clearbrook delivered a solid quarter. Revenue was €1.84 billion, up 6% year on
year, driven by net interest income of €1.21 billion. Diluted earnings per share were €0.92,
compared with €0.81 a year ago. Our CET1 ratio closed at 14.1%.

We are raising our full-year net interest income guidance to between €4.75 and €4.85 billion.
Deposit costs have stabilised, and loan growth in our SME book was 4% quarter on quarter.

CFO: On costs, operating expenses rose 3%, mainly from technology investment in our payments
platform and financial-crime compliance. Impairment charges increased to €96 million, reflecting
some softness in commercial real estate, which we are monitoring closely. The regulator has
also opened a routine review of our provisioning models, and we are cooperating fully.

Analyst Q&A: Asked about rate cuts, the CFO said each 25bp cut would reduce annual net interest
income by roughly €40 million, partly offset by volume growth. On capital, the board will
consider additional buybacks after the regulatory review concludes.

CEO: We remain confident in our outlook for 2027, with continued investment in digital
channels and a disciplined approach to credit risk."""


# ── Demo counterparty network (all entities, people and places are fictional) ──
# flags: sanctioned, pep, secrecy_jurisdiction, adverse_media, shell (separated by ;)
NETWORK_NODES = [
    {"id": "Castellan Construction", "type": "Company", "jurisdiction": "Aldmere", "flags": "adverse_media"},
    {"id": "Port Authority of Aldmere", "type": "Public body", "jurisdiction": "Aldmere", "flags": ""},
    {"id": "Harbourline Trading", "type": "Company", "jurisdiction": "Aldmere", "flags": "adverse_media"},
    {"id": "Meridian Metals", "type": "Company", "jurisdiction": "Corvanna", "flags": "adverse_media"},
    {"id": "Kestrel Holdings", "type": "Shell company", "jurisdiction": "Isle of Varn", "flags": "shell;secrecy_jurisdiction"},
    {"id": "Larkspur Ventures", "type": "Shell company", "jurisdiction": "Isle of Varn", "flags": "shell;secrecy_jurisdiction"},
    {"id": "Northgate Nominees", "type": "Company", "jurisdiction": "Calder Bay", "flags": "secrecy_jurisdiction"},
    {"id": "Ostrava Logistics", "type": "Company", "jurisdiction": "Corvanna", "flags": ""},
    {"id": "Clearbrook Bank", "type": "Bank", "jurisdiction": "Aldmere", "flags": ""},
    {"id": "Silverline Payments", "type": "Bank", "jurisdiction": "Calder Bay", "flags": ""},
    {"id": "Oakridge Foods", "type": "Company", "jurisdiction": "Aldmere", "flags": ""},
    {"id": "Brightwater Capital", "type": "Company", "jurisdiction": "Aldmere", "flags": "adverse_media"},
    {"id": "Volkov Shipping", "type": "Company", "jurisdiction": "Corvanna", "flags": "sanctioned"},
    {"id": "A. Varga", "type": "Person", "jurisdiction": "Aldmere", "flags": "pep"},
    {"id": "R. Doyle", "type": "Person", "jurisdiction": "Aldmere", "flags": ""},
    {"id": "M. Sato", "type": "Person", "jurisdiction": "Calder Bay", "flags": ""},
    {"id": "L. Brennan", "type": "Person", "jurisdiction": "Aldmere", "flags": ""},
    {"id": "E. Marchetti", "type": "Person", "jurisdiction": "Corvanna", "flags": "adverse_media"},
]

NETWORK_EDGES = [
    # source, target, relation, amount (EUR; 0 when not a payment)
    ("Port Authority of Aldmere", "Castellan Construction", "contract", 0),
    ("Castellan Construction", "Kestrel Holdings", "payment", 4_800_000),
    ("Castellan Construction", "Clearbrook Bank", "payment", 900_000),
    ("Kestrel Holdings", "Larkspur Ventures", "payment", 3_100_000),
    ("Larkspur Ventures", "Northgate Nominees", "payment", 2_600_000),
    ("Northgate Nominees", "A. Varga", "owns", 0),
    ("A. Varga", "Port Authority of Aldmere", "director", 0),
    ("M. Sato", "Kestrel Holdings", "director", 0),
    ("M. Sato", "Larkspur Ventures", "director", 0),
    ("M. Sato", "Northgate Nominees", "director", 0),
    ("R. Doyle", "Castellan Construction", "director", 0),
    ("Kestrel Holdings", "Harbourline Trading", "owns", 0),
    ("Harbourline Trading", "Meridian Metals", "payment", 1_400_000),
    ("Meridian Metals", "Volkov Shipping", "contract", 0),
    ("Meridian Metals", "Silverline Payments", "payment", 650_000),
    ("Volkov Shipping", "Silverline Payments", "payment", 1_200_000),
    ("E. Marchetti", "Meridian Metals", "director", 0),
    ("E. Marchetti", "Ostrava Logistics", "owns", 0),
    ("Ostrava Logistics", "Volkov Shipping", "payment", 300_000),
    ("Harbourline Trading", "Clearbrook Bank", "payment", 250_000),
    ("Oakridge Foods", "Clearbrook Bank", "payment", 400_000),
    ("L. Brennan", "Oakridge Foods", "director", 0),
    ("Brightwater Capital", "Larkspur Ventures", "payment", 700_000),
    ("L. Brennan", "Brightwater Capital", "director", 0),
]

# The same edges as CSV text, offered as a download template on the Network page
NETWORK_CSV = "source,target,relation,amount\n" + "\n".join(
    f"{s},{t},{r},{a}" for s, t, r, a in NETWORK_EDGES
)
