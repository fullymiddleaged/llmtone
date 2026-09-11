"""Splicing the block into a file, and refusing to when it looks wrong.

The whole point of the markers is the *second* run, so most of what is here
checks that running twice leaves one block and everything around it untouched.
"""

from __future__ import annotations

import pytest

from llmtone.integrate import (
    END,
    START,
    BlockError,
    refresh_command,
    render_block,
    splice,
    write_block,
)

BLOCK = render_block("Write in this person's voice.\n\n- Concise.")
OTHER = render_block("Write in this person's voice.\n\n- Verbose.")


class TestRenderBlock:
    def test_is_wrapped_in_markers(self):
        assert BLOCK.startswith(START)
        assert BLOCK.endswith(END)

    def test_carries_the_instructions_and_how_to_refresh(self):
        assert "- Concise." in BLOCK
        assert "llmtone prompt --write AGENTS.md" in BLOCK

    def test_a_context_names_itself_in_the_heading_and_the_refresh(self):
        block = render_block("x", context="work", target="CLAUDE.md")
        assert "## Writing voice (work)" in block
        assert "llmtone prompt --context work --write CLAUDE.md" in block

    def test_refresh_command_leaves_context_out_when_there_is_none(self):
        assert refresh_command("AGENTS.md") == "llmtone prompt --write AGENTS.md"


class TestSplice:
    def test_no_file_creates_one_holding_just_the_block(self):
        text, action = splice(None, BLOCK)
        assert action == "created"
        assert text == BLOCK + "\n"

    def test_an_empty_file_counts_as_no_file(self):
        text, action = splice("\n  \n", BLOCK)
        assert action == "created"
        assert text == BLOCK + "\n"

    def test_a_file_without_markers_keeps_its_content_and_gains_a_block(self):
        text, action = splice("# Project\n\nBuild with make.\n", BLOCK)
        assert action == "appended"
        assert text.startswith("# Project\n\nBuild with make.\n\n")
        assert BLOCK in text
        assert text.endswith("\n")

    def test_a_second_run_replaces_rather_than_appends(self):
        once, _ = splice("# Project\n\nBuild with make.\n", BLOCK)
        twice, action = splice(once, OTHER)
        assert action == "replaced"
        assert twice.count(START) == 1
        assert "- Verbose." in twice
        assert "- Concise." not in twice

    def test_replacing_leaves_everything_around_the_block_byte_identical(self):
        before = "# Project\n\nAbove.\n\n"
        after = "\n## Notes\n\nBelow.\n"
        existing = before + BLOCK + after
        text, action = splice(existing, OTHER)
        assert action == "replaced"
        assert text.startswith(before)
        assert text.endswith(after)

    def test_a_block_at_the_end_without_a_trailing_newline_still_ends_with_one(self):
        text, _ = splice("# Project\n\n" + BLOCK, OTHER)
        assert text.endswith("\n")
        assert text.count(END) == 1

    def test_crlf_stays_crlf(self):
        existing = "# Project\r\n\r\nBuild with make.\r\n"
        text, _ = splice(existing, BLOCK)
        assert "\r\n" in text
        assert "\n" not in text.replace("\r\n", "")

    def test_lf_stays_lf(self):
        text, _ = splice("# Project\n", BLOCK)
        assert "\r" not in text

    def test_a_marker_indented_into_a_code_fence_is_documentation_not_a_block(self):
        existing = f"# Project\n\n```\n    {START}\n    {END}\n```\n"
        text, action = splice(existing, BLOCK)
        assert action == "appended"
        assert f"    {START}" in text


class TestSpliceRefuses:
    def test_a_start_with_no_end(self):
        with pytest.raises(BlockError, match="no <!-- llmtone:end -->"):
            splice(f"# Project\n{START}\nstranded\n", BLOCK)

    def test_an_end_with_no_start(self):
        with pytest.raises(BlockError, match="no <!-- llmtone:start -->"):
            splice(f"# Project\nstranded\n{END}\n", BLOCK)

    def test_an_end_before_a_start(self):
        with pytest.raises(BlockError, match="the right way round"):
            splice(f"{END}\nbackwards\n{START}\n", BLOCK)

    def test_two_blocks_because_it_cannot_know_which_one_you_meant(self):
        with pytest.raises(BlockError, match="more than one"):
            splice(BLOCK + "\n" + BLOCK + "\n", OTHER)


class TestWriteBlock:
    def test_creates_the_file(self, tmp_path):
        target = tmp_path / "AGENTS.md"
        assert write_block(target, BLOCK) == "created"
        assert target.read_text(encoding="utf-8") == BLOCK + "\n"

    def test_running_twice_does_not_grow_the_file(self, tmp_path):
        target = tmp_path / "AGENTS.md"
        target.write_text("# Project\n\nBuild with make.\n", encoding="utf-8")
        assert write_block(target, BLOCK) == "appended"
        once = target.read_text(encoding="utf-8")
        assert write_block(target, BLOCK) == "replaced"
        assert target.read_text(encoding="utf-8") == once

    def test_hand_written_text_around_the_block_survives(self, tmp_path):
        target = tmp_path / "AGENTS.md"
        write_block(target, BLOCK)
        edited = "# Mine\n\n" + target.read_text(encoding="utf-8") + "\nKeep me.\n"
        target.write_text(edited, encoding="utf-8")
        write_block(target, OTHER)
        text = target.read_text(encoding="utf-8")
        assert text.startswith("# Mine\n")
        assert text.endswith("Keep me.\n")
        assert "- Verbose." in text

    def test_non_ascii_survives_a_round_trip(self, tmp_path):
        """The instructions name em dashes. A cp1252 default would break here."""
        target = tmp_path / "AGENTS.md"
        target.write_text("# Café — notes\n", encoding="utf-8")
        write_block(target, render_block("- Do not use: em dashes — like this."))
        text = target.read_text(encoding="utf-8")
        assert "Café — notes" in text
        assert "em dashes — like this" in text

    def test_a_crlf_file_is_not_turned_into_mixed_endings(self, tmp_path):
        target = tmp_path / "AGENTS.md"
        with target.open("w", encoding="utf-8", newline="") as handle:
            handle.write("# Project\r\n\r\nBuild with make.\r\n")
        write_block(target, BLOCK)
        raw = target.read_bytes()
        assert raw.count(b"\r\n") == raw.count(b"\n")

    def test_a_file_it_cannot_read_is_left_alone(self, tmp_path):
        target = tmp_path / "a-directory"
        target.mkdir()
        with pytest.raises(BlockError):
            write_block(target, BLOCK)

    def test_a_missing_parent_directory_is_reported_not_raised_raw(self, tmp_path):
        with pytest.raises(BlockError, match="could not write"):
            write_block(tmp_path / "nope" / "AGENTS.md", BLOCK)

    def test_a_file_that_is_not_utf8_is_left_alone(self, tmp_path):
        target = tmp_path / "AGENTS.md"
        target.write_bytes(b"\xff\xfe not utf-8 at all")
        with pytest.raises(BlockError, match="not UTF-8"):
            write_block(target, BLOCK)
        assert target.read_bytes().startswith(b"\xff\xfe")
