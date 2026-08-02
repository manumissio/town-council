import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const homePath = path.resolve(process.cwd(), "app/page.js");
const resultCardPath = path.resolve(process.cwd(), "components/ResultCard.js");
const personProfilePath = path.resolve(process.cwd(), "components/PersonProfile.js");
const homeSource = fs.readFileSync(homePath, "utf8");
const resultCardSource = fs.readFileSync(resultCardPath, "utf8");

test("people projection removes the search-driven profile path", () => {
  assert.equal(fs.existsSync(personProfilePath), false);
  assert.doesNotMatch(homeSource, /PersonProfile|selectedPersonId|onPersonClick/);
  assert.doesNotMatch(
    resultCardSource,
    /people_metadata|showAllOfficials|onPersonClick|UserCircle/,
  );
});
