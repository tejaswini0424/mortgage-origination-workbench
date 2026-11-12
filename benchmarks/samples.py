from pathlib import Path
from .run import fixture, values_for

def main():
    output = Path("runtime/samples")
    output.mkdir(parents=True, exist_ok=True)
    for kind, values in values_for("Fictional Borrower 10000").items():
        (output / f"{kind}.pdf").write_bytes(fixture(kind, values))
    print(output.resolve())

if __name__ == "__main__":
    main()
