#!/usr/bin/env python
"""
CLI script to enrich the B1 question bank with AI-generated questions (Reading, Writing, Speaking).
Supports counting, seeding, and part filtering.

Usage:
    python scripts/enrich_b1_bank.py --count 20 --seed 42 --part all
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
    parser = argparse.ArgumentParser(description="Enrich VSTEP B1 question bank via AI.")
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
        choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "all"],
        default="all",
        help="VSTEP B1 part to generate: 1 (R1), 2 (R2), 3 (R3), 4 (R4), 5 (W1), 6 (W2), 7 (L1), 8 (L2), 9 (S1), 10 (S2), 11 (S3), or all."
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
        
    print("Initializing VSTEP B1 Question Bank Enrichment CLI...")
    print(f"Target count: {args.count} per part")
    print(f"Seed: {args.seed}")
    print(f"Part(s): {args.part}")
    print(f"Topic filter: {args.topic or 'None'}")

    # Ensure tables exist (especially if SQLite database file doesn't exist yet)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    generator = B1QuestionGenerator()

    try:
        # Reading Part 1 (R1 choice standalone)
        if args.part in ("1", "all"):
            print("Generating Reading Part 1 (R1 choice standalone)...")
            r1_count = generator.generate_r1_questions(
                db=db, count=args.count, topic=args.topic, seed=args.seed
            )
            print(f"-> Successfully saved {r1_count} R1 questions to database.")

        # Reading Part 2 (R2 choice notice standalone)
        if args.part in ("2", "all"):
            print("Generating Reading Part 2 (R2 choice notice standalone)...")
            r2_seed = args.seed + 500 if args.seed is not None else None
            r2_count = generator.generate_r2_questions(
                db=db, count=args.count, topic=args.topic, seed=r2_seed
            )
            print(f"-> Successfully saved {r2_count} R2 questions to database.")

        # Reading Part 3 (R3 choice groups)
        if args.part in ("3", "all"):
            print("Generating Reading Part 3 (R3 choice groups)...")
            r3_seed = args.seed + 1000 if args.seed is not None else None
            r3_count = generator.generate_r3_groups(
                db=db, count=args.count, topic=args.topic, seed=r3_seed
            )
            print(f"-> Successfully saved {r3_count} R3 groups to database.")

        # Reading Part 4 (R4 fill groups)
        if args.part in ("4", "all"):
            print("Generating Reading Part 4 (R4 fill groups)...")
            r4_seed = args.seed + 2000 if args.seed is not None else None
            r4_count = generator.generate_r4_groups(
                db=db, count=args.count, topic=args.topic, seed=r4_seed
            )
            print(f"-> Successfully saved {r4_count} R4 groups to database.")

        # Writing Part 5 (W1 sentence transformation)
        if args.part in ("5", "all"):
            print("Generating Writing Part 5 (W1 sentence transformation)...")
            w1_seed = args.seed + 3000 if args.seed is not None else None
            w1_count = generator.generate_writing_questions(
                db=db, count=args.count, part=5, topic=args.topic, seed=w1_seed
            )
            print(f"-> Successfully saved {w1_count} W1 writing questions to database.")

        # Writing Part 6 (W2 essay/email writing)
        if args.part in ("6", "all"):
            print("Generating Writing Part 6 (W2 email/letter writing)...")
            w2_seed = args.seed + 4000 if args.seed is not None else None
            w2_count = generator.generate_writing_questions(
                db=db, count=args.count, part=6, topic=args.topic, seed=w2_seed
            )
            print(f"-> Successfully saved {w2_count} W2 writing questions to database.")

        # Listening Part 7 (L1 choice standalone)
        if args.part in ("7", "all"):
            print("Generating Listening Part 7 (L1 choice standalone)...")
            l1_seed = args.seed + 9000 if args.seed is not None else None
            l1_count = generator.generate_l1_questions(
                db=db, count=args.count, topic=args.topic, seed=l1_seed
            )
            print(f"-> Successfully saved {l1_count} L1 questions to database.")

        # Listening Part 8 (L2 note completion gap-fill)
        if args.part in ("8", "all"):
            print("Generating Listening Part 8 (L2 note completion gap-fill)...")
            l2_seed = args.seed + 8000 if args.seed is not None else None
            l2_count = generator.generate_l2_groups(
                db=db, count=args.count, topic=args.topic, seed=l2_seed
            )
            print(f"-> Successfully saved {l2_count} L2 groups to database.")

        # Speaking Part 9 (S1 social interaction)
        if args.part in ("9", "all"):
            print("Generating Speaking Part 9 (S1 social interaction)...")
            s1_seed = args.seed + 5000 if args.seed is not None else None
            s1_count = generator.generate_speaking_questions(
                db=db, count=args.count, part=9, topic=args.topic, seed=s1_seed
            )
            print(f"-> Successfully saved {s1_count} S1 speaking questions to database.")

        # Speaking Part 10 (S2 solution discussion)
        if args.part in ("10", "all"):
            print("Generating Speaking Part 10 (S2 solution discussion)...")
            s2_seed = args.seed + 6000 if args.seed is not None else None
            s2_count = generator.generate_speaking_questions(
                db=db, count=args.count, part=10, topic=args.topic, seed=s2_seed
            )
            print(f"-> Successfully saved {s2_count} S2 speaking questions to database.")

        # Speaking Part 11 (S3 topic development)
        if args.part in ("11", "all"):
            print("Generating Speaking Part 11 (S3 topic development)...")
            s3_seed = args.seed + 7000 if args.seed is not None else None
            s3_count = generator.generate_speaking_questions(
                db=db, count=args.count, part=11, topic=args.topic, seed=s3_seed
            )
            print(f"-> Successfully saved {s3_count} S3 speaking questions to database.")

        print("Enrichment run completed.")
    except Exception as e:
        print(f"Enrichment run failed: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
