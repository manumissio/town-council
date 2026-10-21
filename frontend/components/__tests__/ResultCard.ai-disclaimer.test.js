import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const filePath = path.resolve(process.cwd(), "components/ResultCard.js");
const source = fs.readFileSync(filePath, "utf8");

test("defines contextual AI disclaimer booleans", () => {
  assert.match(
    source,
    /const hasSummaryPayload = Boolean\(\(summary && summary\.trim\(\)\) \|\| \(hit\.summary_extractive && hit\.summary_extractive\.trim\(\)\)\);/,
  );
  assert.match(source, /const hasTopicsPayload = Boolean\(topics && topics\.length > 0\);/);
  assert.match(source, /const showAiDisclaimer = viewMode === "summary" && \(hasSummaryPayload \|\| hasTopicsPayload\);/);
});

test("renders one top-level disclaimer with neutral palette and Info icon", () => {
  assert.match(source, /\{showAiDisclaimer && \(/);
  assert.match(source, /border-slate-200 bg-slate-50/);
  assert.match(source, /text-slate-600/);
  assert.match(source, /<Info className="w-3\.5 h-3\.5 shrink-0 text-slate-500" \/>/);
});

test("uses canonical disclaimer copy", () => {
  assert.match(
    source,
    /const AI_DISCLAIMER_TEXT = "AI-generated content may be incomplete or inaccurate\. Verify against source documents\.";/,
  );
});

test("freshness never claims that a summary is factually verified", () => {
  assert.doesNotMatch(source, /summaryGrounded|>\s*Grounded\s*</);
  assert.match(source, /Freshness unknown/);
  assert.doesNotMatch(source, /Matches current source version/);
});

test("unattempted and failed segmentation do not claim no business exists", () => {
  assert.match(source, /Agenda items unavailable/);
  assert.match(source, /Segmentation failed/);
  assert.match(source, /This document has not been segmented yet/);
});
