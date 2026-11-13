"""Fail when a value this repository copies from an upstream pin has drifted."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_env

SUPERPOWERS = local_env.RUNTIME_ROOT / "superpowers"
EXTENSION = Path(__file__).resolve().parent / "pi-extensions/forge-workspace"


def quoted_constant(source, name):
    match = re.search(rf'\b{name}\s*=\s*"([^"\n]+)"', source)
    return match.group(1) if match else None


@unittest.skipUnless((SUPERPOWERS / "skills").is_dir(), "superpowers submodule not checked out")
class SuperpowersDriftTests(unittest.TestCase):
    def test_bootstrap_marker_matches_pinned_superpowers(self):
        upstream = quoted_constant((SUPERPOWERS / ".pi/extensions/superpowers.ts").read_text(), "BOOTSTRAP_MARKER")
        ours = quoted_constant((EXTENSION / "superpowers.ts").read_text(), "BOOTSTRAP_MARKER")
        self.assertIsNotNone(upstream)
        self.assertEqual(ours, upstream)

    def test_overridden_skills_still_exist_under_their_names(self):
        index = (EXTENSION / "index.ts").read_text()
        block = re.search(r"SKILL_OVERRIDES[^{]*\{(.*?)\n\};", index, re.S).group(1)
        names = re.findall(r'^\s*"?([\w-]+)"?:', block, re.M)
        self.assertEqual(len(names), 3)
        for name in names:
            skill = SUPERPOWERS / "skills" / name / "SKILL.md"
            self.assertTrue(skill.is_file(), name)
            self.assertRegex(skill.read_text(), rf"(?m)^name:\s*{re.escape(name)}\s*$")


if __name__ == "__main__":
    unittest.main()
