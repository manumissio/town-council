/**
 * UI-only text formatter for extracted document text.
 *
 * Why this lives in the frontend:
 * - We keep raw extracted text in the DB for indexing and AI tasks.
 * - We only improve readability at render time.
 */
function normalizeWhitespace(text) {
  if (!text) return "";

  const normalizedLineEndings = String(text).replace(/\r\n?/g, "\n");
  const lines = normalizedLineEndings.split("\n").map((line) => line.replace(/\s+$/g, ""));

  const compactLines = [];
  let previousWasBlank = false;

  for (const rawLine of lines) {
    const trimmed = rawLine.trim();

    if (!trimmed) {
      if (!previousWasBlank) compactLines.push("");
      previousWasBlank = true;
      continue;
    }

    // Collapse excessive in-line whitespace while preserving line order.
    const collapsed = trimmed.replace(/\s{2,}/g, " ");
    compactLines.push(collapsed);
    previousWasBlank = false;
  }

  return compactLines.join("\n").trim();
}

function splitByPageMarkers(text) {
  const normalized = normalizeWhitespace(text);
  if (!normalized) return [];

  const markerRegex = /^\[PAGE\s+(\d+)\]$/i;
  const sections = [];
  let current = { pageNumber: null, lines: [] };

  for (const line of normalized.split("\n")) {
    const markerMatch = line.match(markerRegex);
    if (markerMatch) {
      if (current.lines.length > 0 || current.pageNumber !== null) {
        sections.push(current);
      }
      current = { pageNumber: Number(markerMatch[1]), lines: [] };
      continue;
    }
    current.lines.push(line);
  }

  if (current.lines.length > 0 || current.pageNumber !== null) {
    sections.push(current);
  }

  return sections;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function isListLine(line) {
  return /^([-*]|\d+[.)])\s+/.test(line);
}

function renderBlock(lines) {
  if (!lines.length) return "";

  const allListLines = lines.every(isListLine);
  if (allListLines) {
    const items = lines
      .map((line) => line.replace(/^([-*]|\d+[.)])\s+/, ""))
      .filter(Boolean)
      .map((line) => `<li>${escapeHtml(line)}</li>`)
      .join("");
    return `<ul class=\"list-disc pl-6 my-2 space-y-1\">${items}</ul>`;
  }

  // Join wrapped lines into readable paragraphs.
  const paragraph = escapeHtml(lines.join(" "));
  return `<p class=\"leading-relaxed my-2\">${paragraph}</p>`;
}

function renderSection(section, index) {
  const parts = [];

  if (section.pageNumber !== null) {
    parts.push(
      `<div class=\"mt-4 mb-2 pt-3 border-t border-gray-200 text-[11px] font-bold uppercase tracking-widest text-gray-500\">Page ${section.pageNumber}</div>`
    );
  } else if (index > 0) {
    parts.push(`<div class=\"my-2 border-t border-gray-100\"></div>`);
  }

  const blocks = [];
  let currentBlock = [];
  for (const line of section.lines) {
    if (!line) {
      if (currentBlock.length) {
        blocks.push(currentBlock);
        currentBlock = [];
      }
      continue;
    }
    currentBlock.push(line);
  }
  if (currentBlock.length) blocks.push(currentBlock);

  for (const block of blocks) {
    parts.push(renderBlock(block));
  }

  return parts.join("");
}

function renderFormattedExtractedText(text) {
  const sections = splitByPageMarkers(text);
  if (!sections.length) return "";

  return sections.map((section, index) => renderSection(section, index)).join("");
}

module.exports = {
  normalizeWhitespace,
  splitByPageMarkers,
  renderFormattedExtractedText,
};
