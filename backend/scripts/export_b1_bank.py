"""
Export B1 Bank: Dump VSTEP B1 questions and question groups (where exam_id IS NULL)
from the local database to a portable JSON file, listing any static asset files (audio/img)
referenced so they can be packaged together.
"""
import os
import sys
import json

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.database import SessionLocal  # noqa: E402
from app.models.question import Question  # noqa: E402
from app.models.question_group import QuestionGroup  # noqa: E402


def get_relative_asset_path(url: str) -> list[str]:
    """Extract relative static asset paths from a database URL.
    Handles comma-separated multi-image URLs as well.
    """
    if not url:
        return []
    paths = []
    # Handle possible multi-image URLs (split by comma)
    parts = [p.strip() for p in url.split(",") if p.strip()]
    for part in parts:
        # We only care about local static files starting with "/static/"
        if part.startswith("/static/"):
            # Convert "/static/..." -> "static/..." relative to backend directory
            paths.append(part.lstrip("/"))
    return paths


def main():
    print("Exporting VSTEP B1 bank questions...")
    db = SessionLocal()
    try:
        # Query all bank questions of VSTEP_B1
        questions = db.query(Question).filter(
            Question.exam_id.is_(None),
            Question.exam_type == "VSTEP_B1"
        ).all()

        print(f"Found {len(questions)} VSTEP B1 bank questions.")

        groups_map = {}
        standalone_questions = []
        referenced_assets = set()

        for q in questions:
            # Map question details
            q_dict = {
                "part": q.part,
                "type": q.type,
                "content": q.content,
                "audio_url": q.audio_url,
                "image_url": q.image_url,
                "options": q.options,
                "reference_answer": q.reference_answer,
                "difficulty": q.difficulty,
                "clo": q.clo,
                "topic": q.topic,
                "status": q.status,
                "explanation": q.explanation,
                "exam_type": q.exam_type,
                "language": q.language,
                "content_hash": q.content_hash,
            }

            # Collect referenced assets from question fields
            referenced_assets.update(get_relative_asset_path(q.audio_url))
            referenced_assets.update(get_relative_asset_path(q.image_url))

            if q.group_id is not None:
                if q.group_id not in groups_map:
                    # Fetch parent group
                    g = db.query(QuestionGroup).filter(QuestionGroup.id == q.group_id).first()
                    if g:
                        g_dict = {
                            "id_original": g.id, # keeping to map correctly
                            "part": g.part,
                            "topic": g.topic,
                            "passage_text": g.passage_text,
                            "audio_url": g.audio_url,
                            "image_url": g.image_url,
                            "passage_type": g.passage_type,
                            "speaker_count": g.speaker_count,
                            "speech_rate": g.speech_rate,
                            "accent": g.accent,
                            "difficulty": g.difficulty,
                            "status": g.status,
                            "content_hash": g.content_hash,
                            "questions": []
                        }
                        # Collect referenced assets from group fields
                        referenced_assets.update(get_relative_asset_path(g.audio_url))
                        referenced_assets.update(get_relative_asset_path(g.image_url))
                        groups_map[q.group_id] = g_dict
                    else:
                        print(f"Warning: Question #{q.id} points to non-existent group #{q.group_id}. Treating as standalone.")
                        standalone_questions.append(q_dict)
                        continue

                groups_map[q.group_id]["questions"].append(q_dict)
            else:
                standalone_questions.append(q_dict)

        # Convert groups map to list and clean up original IDs
        groups_list = []
        for g_dict in groups_map.values():
            # sort child questions by content or order if necessary, but keep original order
            # remove original id to keep it pure portable
            g_dict.pop("id_original", None)
            groups_list.append(g_dict)

        # Build final package
        package = {
            "groups": groups_list,
            "standalone_questions": standalone_questions,
            "assets": sorted(list(referenced_assets))
        }

        # Write to JSON
        export_path = os.path.join(BACKEND_DIR, "scripts", "b1_bank_export.json")
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(package, f, indent=2, ensure_ascii=False)

        print(f"Successfully exported bank to: {export_path}")
        print(f"  Groups: {len(groups_list)}")
        print(f"  Standalone Questions: {len(standalone_questions)}")
        print(f"  Referenced assets found: {len(referenced_assets)}")
        
        # Verify physical existence of assets
        missing_assets = []
        for asset in package["assets"]:
            full_path = os.path.join(BACKEND_DIR, asset)
            if not os.path.isfile(full_path):
                missing_assets.append(asset)
        
        if missing_assets:
            print("\nWarning: The following referenced assets are missing from local filesystem:")
            for ma in missing_assets:
                print(f"  - {ma}")
        else:
            print("\nAll assets exist locally on disk and are ready for packaging.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
