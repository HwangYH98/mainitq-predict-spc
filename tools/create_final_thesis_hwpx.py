"""Create a Hangul HWPX thesis draft from the generated thesis content.

This script avoids storing secrets and does not depend on a live API key.  It
builds a simple HWPX package from a blank HWPX produced by Hancom Office and
fills the section XML with 29 page blocks.
"""

from __future__ import annotations

import html
import re
import shutil
import textwrap
import zipfile
from pathlib import Path

from create_final_thesis_manuscript import collect_evidence, thesis_pages


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
BLANK = OUTPUTS / "blank_test.hwpx"
HWPX_PATH = OUTPUTS / "final_thesis_manuscript_29p.hwpx"
LOG_PATH = OUTPUTS / "final_thesis_hwpx_build_log.txt"

NS_DECL = (
    'xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
    'xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph" '
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" '
    'xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
    'xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history" '
    'xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page" '
    'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:opf="http://www.idpf.org/2007/opf/" '
    'xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart" '
    'xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar" '
    'xmlns:epub="http://www.idpf.org/2007/ops" '
    'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0"'
)


def _sec_pr_from_blank() -> str:
    with zipfile.ZipFile(BLANK) as archive:
        section = archive.read("Contents/section0.xml").decode("utf-8")
    match = re.search(r"(<hp:secPr\b.*?</hp:secPr><hp:ctrl>.*?</hp:ctrl>)", section)
    if not match:
        raise RuntimeError("Could not extract section properties from blank HWPX.")
    sec_pr = match.group(1)
    # Match thesis-writing guide margins: top 35, left 35, right 30, bottom 25,
    # footer 15 mm. HWP unit is approximately 283.465 units per mm.
    margin = '<hp:margin header="0" footer="4252" gutter="0" left="9921" right="8504" top="9921" bottom="7087"/>'
    sec_pr = re.sub(r"<hp:margin\b[^/]*/>", margin, sec_pr)
    return sec_pr


def xml_text(text: str) -> str:
    return html.escape(str(text), quote=False)


def paragraph_xml(text: str, pid: int, page_break: bool = False, char_pr: int = 0, para_pr: int = 0) -> str:
    return (
        f'<hp:p id="{pid}" paraPrIDRef="{para_pr}" styleIDRef="0" pageBreak="{1 if page_break else 0}" '
        f'columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{char_pr}"><hp:t>{xml_text(text)}</hp:t></hp:run>'
        f'<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="1000" '
        f'textheight="1000" baseline="850" spacing="1600" horzpos="0" horzsize="42520" '
        f'flags="393216"/></hp:linesegarray></hp:p>'
    )


def split_for_hwp(text: str, width: int = 92) -> list[str]:
    """Keep each hp:t node short enough for stable HWP layout recalculation."""
    value = " ".join(str(text).split())
    if not value:
        return []
    return textwrap.wrap(value, width=width, break_long_words=False, break_on_hyphens=False) or [value]


def build_section_xml(pages: list[dict]) -> str:
    sec_pr = _sec_pr_from_blank()
    parts = [f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {NS_DECL}>']
    pid = 1000000
    parts.append(
        f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="0">{sec_pr}</hp:run>'
        f'<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" '
        f'baseline="850" spacing="1600" horzpos="0" horzsize="42520" flags="393216"/></hp:linesegarray></hp:p>'
    )
    pid += 1

    for idx, page in enumerate(pages, start=1):
        parts.append(paragraph_xml(f"[{idx}] {page['title']}", pid, page_break=(idx != 1), char_pr=0))
        pid += 1
        for para in page.get("paras", []):
            for line in str(para).splitlines():
                for chunk in split_for_hwp(line):
                    parts.append(paragraph_xml(chunk, pid))
                    pid += 1
        if "table" in page:
            headers, rows = page["table"]
            for chunk in split_for_hwp("표. " + " | ".join(headers)):
                parts.append(paragraph_xml(chunk, pid))
                pid += 1
            for row in rows:
                for chunk in split_for_hwp(" | ".join(row)):
                    parts.append(paragraph_xml(chunk, pid))
                    pid += 1
        if "figure" in page:
            image_name, caption = page["figure"]
            for chunk in split_for_hwp(f"{caption} (그림 원본: outputs/{image_name})"):
                parts.append(paragraph_xml(chunk, pid))
                pid += 1
    parts.append("</hs:sec>")
    return "".join(parts)


def preview_text(pages: list[dict]) -> str:
    lines: list[str] = []
    for idx, page in enumerate(pages, start=1):
        lines.append(f"[{idx}] {page['title']}")
        for para in page.get("paras", [])[:2]:
            lines.append(str(para)[:180])
    return "\n".join(lines)


def build_hwpx() -> None:
    if not BLANK.exists():
        raise FileNotFoundError(f"Blank HWPX template missing: {BLANK}")
    pages = thesis_pages(collect_evidence())
    if len(pages) == 31:
        limitation_page = pages.pop(28)
        pages[27]["paras"].extend(limitation_page["paras"])
        pages.pop(-1)
    if len(pages) != 29:
        raise AssertionError(f"Expected 29 page blocks, got {len(pages)}")

    section_xml = build_section_xml(pages)
    preview = preview_text(pages)

    temp = HWPX_PATH.with_suffix(".tmp.hwpx")
    if temp.exists():
        temp.unlink()
    with zipfile.ZipFile(BLANK, "r") as src, zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "Contents/section0.xml":
                data = section_xml.encode("utf-8")
            elif item.filename == "Preview/PrvText.txt":
                data = preview.encode("utf-8")
            dst.writestr(item, data)

    if HWPX_PATH.exists():
        HWPX_PATH.unlink()
    shutil.move(str(temp), str(HWPX_PATH))
    LOG_PATH.write_text(
        f"HWPX generated: {HWPX_PATH}\nsize={HWPX_PATH.stat().st_size}\npage_blocks={len(pages)}\n",
        encoding="utf-8",
    )
    print(f"HWPX: {HWPX_PATH}")
    print(f"page_blocks={len(pages)}")
    print(f"size={HWPX_PATH.stat().st_size}")


if __name__ == "__main__":
    build_hwpx()
