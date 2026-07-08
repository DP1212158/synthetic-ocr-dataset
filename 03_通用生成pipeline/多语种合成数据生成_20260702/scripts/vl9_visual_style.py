"""VL9 visual cleanup CSS.

VL9 keeps the VL7 template-declared reading flow, but removes ordinary text
container frames and dense divider lines. Semantic structures such as tables,
certificates, forms, answer areas, and image placeholders keep their borders.
"""

from __future__ import annotations


def is_vl9(version_name: str | None) -> bool:
    return str(version_name or "").upper() == "VL9"


def apply_vl9_visual_cleanup(css: str, version_name: str | None) -> str:
    if not is_vl9(version_name):
        return css
    return css + """

    /* VL9 cleanup: ordinary text should not look boxed or ruled. */
    .masthead,
    .masthead-split,
    .masthead-minimal,
    .masthead-compact,
    .masthead-banner,
    .special-masthead,
    .issue-bar,
    .story,
    .sidebar,
    .brief-strip,
    .related-strip,
    .metric-strip,
    .community-box,
    .fact-box,
    .calendar-box,
    .contact-box,
    .small-ad-box,
    .digest-card,
    .timeline-item,
    .micro-ad,
    .footer,
    .running-header,
    .folio,
    .book-columns,
    .opener,
    .reading-map,
    .reading-map-item,
    .figure-note,
    .followups,
    .followup,
    .side-note,
    .contents-title,
    .toc-row,
    .extract,
    .lesson-head,
    .key-box,
    .hint,
    .check-box,
    .check-line,
    .callout,
    .vocab-head,
    .exercise-head,
    .point,
    .mini-ex,
    .summary-box,
    .concept-card,
    .term,
    .activity-head,
    .step,
    .review-card,
    .short-block,
    .feature-bottom,
    .feature-card,
    .cover-line,
    .cover-dept,
    .pull-quote,
    .journal-entry,
    .column-head,
    .side-digest,
    .module-head,
    .module,
    .paper-head,
    .abstract,
    .keyword,
    .paper-footnotes,
    .paper-footnote,
    .analysis-notes,
    .analysis-note,
    .metric,
    .appendix,
    .appendix-row,
    .ref-item,
    .review-box,
    .review-notes,
    .review-note,
    .comment,
    .classic-frame header,
    .classic-cols,
    .colophon,
    .sutra-note,
    .archive header,
    .archive-kv,
    .clip,
    .main-clip,
    .collation header,
    .notes,
    .note-row,
    .notice-head,
    .notice-appendix,
    .notice-item,
    .meeting-head,
    .agenda,
    .attachments,
    .attachment,
    .notice-signs,
    .notice-sign,
    .public-notice,
    .public-notice .doc-title,
    .timeline,
    .node,
    .remarks,
    .intro,
    .survey-q,
    .archive-card,
    .card-field,
    .declaration,
    .letter,
    .postscript,
    .note-line,
    .bottom-notes,
    .sticky,
    .memo,
    .memo .doc-title,
    .todo {
      border: 0 !important;
      border-top: 0 !important;
      border-right: 0 !important;
      border-bottom: 0 !important;
      border-left: 0 !important;
      box-shadow: none !important;
    }

    .strip-item,
    .sidebar,
    .community-box,
    .fact-box,
    .calendar-box,
    .contact-box,
    .small-ad-box,
    .digest-card,
    .followup,
    .review-card,
    .concept-card,
    .cover-dept,
    .key-box,
    .hint,
    .check-box,
    .pull-quote,
    .module,
    .extract,
    .review-box,
    .remarks,
    .notice-sign,
    .card-field,
    .declaration,
    .sticky {
      background: transparent !important;
    }

    .story,
    .timeline-item,
    .toc-row,
    .journal-entry,
    .notice-item,
    .attachment,
    .node,
    .term,
    .point,
    .mini-ex,
    .step,
    .ref-item,
    .note-row,
    .todo {
      padding-bottom: 2px !important;
    }

    .brief-strip,
    .related-strip,
    .metric-strip,
    .followups,
    .feature-bottom,
    .attachments,
    .notice-signs,
    .paper-footnotes,
    .analysis-notes,
    .review-notes,
    .bottom-notes {
      padding-top: 4px !important;
    }

    .rule {
      display: none !important;
      height: 0 !important;
      margin: 0 !important;
      padding: 0 !important;
      border: 0 !important;
      background: transparent !important;
      box-shadow: none !important;
    }
    """
