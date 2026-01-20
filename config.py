"""
Configuration file - contains all configuration options
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent

# Data directory
DATA_DIR = Path(os.path.join(str(PROJECT_ROOT), "data"))
DATA_DIR.mkdir(exist_ok=True)

# Default output directory (can be overridden by user preference)
DEFAULT_OUTPUT_DIR = Path(os.path.join(str(PROJECT_ROOT), "outputs"))
DEFAULT_OUTPUT_DIR.mkdir(exist_ok=True)

# Preferences file path
PREFERENCES_FILE = Path(os.path.join(str(DATA_DIR), "preferences.json"))

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Default arXiv AI-related categories
DEFAULT_ARXIV_CATEGORIES = [
    "cs.AI",  # Artificial Intelligence
    "cs.LG",  # Machine Learning
    "cs.CL",  # Computation and Language (NLP)
    "cs.CV",  # Computer Vision
    "cs.NE",  # Neural and Evolutionary Computing
    "cs.RO",  # Robotics
    "cs.IR",  # Information Retrieval
    "stat.ML",  # Machine Learning (Statistics)
]

# All available categories for selection
ALL_ARXIV_CATEGORIES = {
    "Computer Science": {
        "cs.AI": "Artificial Intelligence",
        "cs.LG": "Machine Learning",
        "cs.CL": "Computation and Language (NLP)",
        "cs.CV": "Computer Vision",
        "cs.NE": "Neural and Evolutionary Computing",
        "cs.RO": "Robotics",
        "cs.IR": "Information Retrieval",
        "cs.HC": "Human-Computer Interaction",
        "cs.MA": "Multiagent Systems",
        "cs.CR": "Cryptography and Security",
        "cs.DC": "Distributed, Parallel, and Cluster Computing",
        "cs.SE": "Software Engineering",
        "cs.DB": "Databases",
        "cs.SI": "Social and Information Networks",
        "cs.DL": "Digital Libraries",
        "cs.CC": "Computational Complexity",
        "cs.CE": "Computational Engineering, Finance, and Science",
        "cs.CG": "Computational Geometry",
        "cs.GT": "Computer Science and Game Theory",
        "cs.CY": "Computers and Society",
        "cs.DS": "Data Structures and Algorithms",
        "cs.ET": "Emerging Technologies",
        "cs.FL": "Formal Languages and Automata Theory",
        "cs.GL": "General Literature",
        "cs.GR": "Graphics",
        "cs.IT": "Information Theory",
        "cs.LO": "Logic in Computer Science",
        "cs.MS": "Mathematical Software",
        "cs.NI": "Networking and Internet Architecture",
        "cs.OH": "Other Computer Science",
        "cs.OS": "Operating Systems",
        "cs.PF": "Performance",
        "cs.PL": "Programming Languages",
        "cs.SC": "Symbolic Computation",
        "cs.SD": "Sound",
        "cs.SY": "Systems and Control",
    },
    "Economics": {
        "econ.EM": "Econometrics",
        "econ.GN": "General Economics",
        "econ.TH": "Theoretical Economics",
    },
    "Electrical Engineering and Systems Science": {
        "eess.AS": "Audio and Speech Processing",
        "eess.IV": "Image and Video Processing",
        "eess.SP": "Signal Processing",
        "eess.SY": "Systems and Control",
    },
    "Mathematics": {
        "math.OC": "Optimization and Control",
        "math.ST": "Statistics Theory",
        "math.PR": "Probability",
        "math.AG": "Algebraic Geometry",
        "math.AT": "Algebraic Topology",
        "math.AP": "Analysis of PDEs",
        "math.CT": "Category Theory",
        "math.CA": "Classical Analysis and ODEs",
        "math.CO": "Combinatorics",
        "math.AC": "Commutative Algebra",
        "math.CV": "Complex Variables",
        "math.DG": "Differential Geometry",
        "math.DS": "Dynamical Systems",
        "math.FA": "Functional Analysis",
        "math.GM": "General Mathematics",
        "math.GN": "General Topology",
        "math.GR": "Group Theory",
        "math.HO": "History and Overview",
        "math.IT": "Information Theory",
        "math.KT": "K-Theory and Homology",
        "math.LO": "Logic",
        "math.MG": "Metric Geometry",
        "math.MP": "Mathematical Physics",
        "math.NT": "Number Theory",
        "math.NA": "Numerical Analysis",
        "math.OA": "Operator Algebras",
        "math.QA": "Quantum Algebra",
        "math.RT": "Representation Theory",
        "math.RA": "Rings and Algebras",
        "math.SP": "Spectral Theory",
        "math.SG": "Symplectic Geometry",
    },
    "Physics": {
        "quant-ph": "Quantum Physics",
        "physics.comp-ph": "Computational Physics",
        "physics.data-an": "Data Analysis, Statistics and Probability",
        "physics.soc-ph": "Physics and Society",
    },
    "Statistics": {
        "stat.ML": "Machine Learning (Statistics)",
        "stat.TH": "Statistics Theory",
        "stat.ME": "Methodology",
        "stat.AP": "Applications",
        "stat.CO": "Computation",
        "stat.OT": "Other Statistics",
    },
}

# Default time range options
DEFAULT_TIME_RANGES = {
    "today": "Today",
    "3days": "Last 3 days",
    "week": "Last week",
    "2weeks": "Last 2 weeks",
    "month": "Last month",
}

# Maximum results per query
MAX_RESULTS = 200

# Default search mode ("keyword" or "exhaustive")
DEFAULT_SEARCH_MODE = "exhaustive"

# Pagination size for exhaustive arXiv fetching
PAGINATION_SIZE = 200

# Maximum workers for parallel processing
MAX_WORKERS = 32

# Default save user interests and search history
SAVE_TO_LOCAL = True

# Default save results to file
SAVE_RESULTS_TO_FILE = True

# Default maximum number of papers to display (None = unlimited)
MAX_DISPLAY_PAPERS = 20

# Interest score threshold (0-10, only show papers with score above this)
INTEREST_THRESHOLD = 5.0

# Auto-generate summary for search results (adds a brief overview at the top)
AUTO_SUMMARY = True

# Maximum number of top papers to include in auto-summary
SUMMARY_TOP_PAPERS = 10
