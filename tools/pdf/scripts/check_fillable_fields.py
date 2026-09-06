import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pypdf import PdfReader


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: check_fillable_fields.py [input pdf]")
        return 0 if len(sys.argv) == 2 else 2
    reader = PdfReader(sys.argv[1])
    if reader.get_fields():
        print("This PDF has fillable form fields")
    else:
        print("This PDF does not have fillable form fields; you will need to visually determine where to enter data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
