from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGETS = [
    ROOT / "release" / "MaintiQ_Predict_Setup.exe",
    ROOT / "release" / "MaintiQ_Predict_Lite_Setup.exe",
]


def powershell_signature_status(path: Path) -> dict[str, str]:
    if not path.exists():
        return {"path": str(path), "exists": "false", "status": "missing", "subject": "", "issuer": ""}

    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        (
            "$sig = Get-AuthenticodeSignature -LiteralPath "
            + json.dumps(str(path))
            + "; [PSCustomObject]@{"
            + "Status=$sig.Status.ToString();"
            + "StatusMessage=$sig.StatusMessage;"
            + "Subject=if($sig.SignerCertificate){$sig.SignerCertificate.Subject}else{''};"
            + "Issuer=if($sig.SignerCertificate){$sig.SignerCertificate.Issuer}else{''}"
            + "} | ConvertTo-Json -Compress"
        ),
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return {
            "path": str(path),
            "exists": "true",
            "status": "check_failed",
            "subject": "",
            "issuer": "",
            "error": (result.stderr or result.stdout).strip(),
        }
    payload = json.loads(result.stdout)
    return {
        "path": str(path),
        "exists": "true",
        "status": str(payload.get("Status", "")),
        "status_message": str(payload.get("StatusMessage", "")),
        "subject": str(payload.get("Subject", "")),
        "issuer": str(payload.get("Issuer", "")),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Authenticode signing status for MaintiQ Predict installers.")
    parser.add_argument("targets", nargs="*", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--require-signed", action="store_true", help="Fail if any existing installer is not signed and valid.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    statuses = [powershell_signature_status(path) for path in args.targets]
    for item in statuses:
        print(f"{item['path']}")
        print(f"  exists: {item['exists']}")
        print(f"  status: {item['status']}")
        if item.get("subject"):
            print(f"  subject: {item['subject']}")
        if item.get("issuer"):
            print(f"  issuer: {item['issuer']}")
    if args.require_signed:
        bad = [item for item in statuses if item.get("exists") == "true" and item.get("status") != "Valid"]
        if bad:
            print("Signing status check failed: one or more installers are not Valid.", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

