#!/usr/bin/env python
"""
CLI script to enrich the B1 Reading question bank with AI-generated questions (R1, R3, R4).
Supports counting, seeding, and part filtering.

Usage:
    python scripts/enrich_b1_reading.py --count 20 --seed 42 --part all
"""
import argparse
import os
import sys

# Ensure backend directory is in python path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.database import SessionLocal, Base, engine  # noqa: E402
from app.services.b1_question_gen import B1QuestionGenerator, B1_TOPICS  # noqa: E402

def parse_args():
    parser = argparse.ArgumentParser(description="Enrich VSTEP B1 reading question bank via AI.")
    parser.add_argument(
        "--count",
        type=int,
        default=20,
        help="Number of items (standalone questions or groups) to generate per part."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for deterministic generation (especially in mock fallback mode)."
    )
    parser.add_argument(
        "--part",
        type=str,
        choices=["1", "3", "4", "all"],
        default="all",
        help="VSTEP B1 Reading part to generate: 1 (R1), 3 (R3), 4 (R4), or all."
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help=f"Specific topic to focus on (choices: {', '.join(B1_TOPICS)})."
    )
    return parser.parse_args()

def main():
    args = parse_args()
    
    if args.topic and args.topic not in B1_TOPICS:
        print(f"Error: Invalid topic '{args.topic}'. Topic must be one of: {', '.join(B1_TOPICS)}")
        sys.exit(1)
        
    print("Initializing VSTEP B1 Reading Question Enrichment CLI...")
    print(f"Target count: {args.count} per part")
    print(f"Seed: {args.seed}")
    print(f"Part(s): {args.part}")
    print(f"Topic filter: {args.topic or 'None'}")

    # Ensure tables exist (especially if SQLite database file doesn't exist yet)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    generator = B1QuestionGenerator()

    try:
        if args.part in ("1", "all"):
            print("Generating Reading Part 1 (R1 choice standalone)...")
            r1_count = generator.generate_r1_questions(
                db=db, count=args.count, topic=args.topic, seed=args.seed
            )
            print(f"-> Successfully saved {r1_count} R1 questions to database.")

        if args.part in ("3", "all"):
            print("Generating Reading Part 3 (R3 choice groups)...")
            # For groups, use the seed if provided
            # We offset the seed slightly for part 3 and 4 to avoid generating identical contents
            r3_seed = args.seed + 1000 if args.seed is not None else None
            r3_count = generator.generate_r3_groups(
                db=db, count=args.count, topic=args.topic, seed=r3_seed
            )
            print(f"-> Successfully saved {r3_count} R3 groups to database.")

        if args.part in ("4", "all"):
            print("Generating Reading Part 4 (R4 fill groups)...")
            r4_seed = args.seed + 2000 if args.seed is not None else None
            r4_count = generator.generate_r4_groups(
                db=db, count=args.count, topic=args.topic, seed=r4_seed
            )
            print(f"-> Successfully saved {r4_count} R4 groups to database.")

        print("Enrichment run completed.")
    except Exception as e:
        print(f"Enrichment run failed: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
