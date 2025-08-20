import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from app.services.review.analyzer import CodeAnalyzer

async def test_review():
    sample_diff = """
    - def add(a, b):
    -     return a + b
    + def add(a, b):
    +     # Added logging
    +     print(f"Adding {a} and {b}")
    +     return a + b
    """
    analyzer = CodeAnalyzer()
    review = await analyzer.analyze_diff(sample_diff)
    print("LLM Review Output:\n", review)

if __name__ == "__main__":
    asyncio.run(test_review())
