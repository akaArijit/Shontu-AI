import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_UPLOAD_BYTES,
  formatFileSize,
  validateUploadFile,
} from "../src/lib/upload.ts";

function file(name, size) {
  return { name, size };
}

test("accepts supported non-empty files within the upload limit", () => {
  assert.equal(validateUploadFile(file("Client Details.xlsx", 1024)), null);
  assert.equal(validateUploadFile(file("Transaction Statement.CSV", 2048)), null);
});

test("rejects unsupported, empty and oversized files with readable text", () => {
  assert.match(
    validateUploadFile(file("Client Details.txt", 1024)),
    /is not an \.xlsx or \.csv file/,
  );
  assert.match(
    validateUploadFile(file("Client Details.xlsx", 0)),
    /is empty/,
  );
  const oversized = validateUploadFile(
    file("Folios.xlsx", MAX_UPLOAD_BYTES + 1),
  );
  assert.match(oversized, /Files must be 25 MB or smaller/);
  assert.match(oversized, /25\.0 MB/);
});

test("formats file sizes without exposing raw byte counts for large files", () => {
  assert.equal(formatFileSize(900), "900 B");
  assert.equal(formatFileSize(1536), "1.5 KB");
  assert.equal(formatFileSize(25 * 1024 * 1024), "25.0 MB");
});
