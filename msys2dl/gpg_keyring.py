import re
import tempfile
from pathlib import Path

from msys2dl.utilities import run_subprocess


class GpgKeybox:
    def __init__(self, location: str | Path):
        self.location = Path(location).absolute()

    def update_keys(self, key_file: Path | bytes) -> None:
        if isinstance(key_file, Path):
            key_file = key_file.read_bytes()
        text_content = key_file.decode("utf-8")

        # filter out revoked keys
        ok_blocks = []
        blocks = re.findall(
            r"-+BEGIN PGP PUBLIC KEY BLOCK-+.*?-+END PGP PUBLIC KEY BLOCK-+", text_content, flags=re.DOTALL
        )
        for block in blocks:
            if "revoked" not in block:
                ok_blocks.append(block)
        text_content = "\n".join(ok_blocks)

        # Regenerate keybox file
        with tempfile.TemporaryDirectory(prefix="msys2-keys-") as d:
            temp_file_path = Path(d) / "keys.gpg"
            temp_file_path.write_text(text_content, "utf-8")
            self._run_gpg(["--batch", "--yes", "-o", str(self.location), "--dearmor", str(temp_file_path)])

    def validate_signature(self, sig_file: Path, file: Path) -> None:
        self._run_gpg(["--verify", str(sig_file), str(file)])

    def _run_gpg(self, args: list[str]) -> None:
        run_subprocess(["gpg", "--no-default-keyring", "--keyring", str(self.location), *args])
