import { describe, expect, it } from "bun:test";
import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const logScript = join(import.meta.dir, "log.sh");

const append = (file: string, cells: readonly string[]): Promise<number> =>
  new Promise((resolve, reject) => {
    const child = spawn(logScript, [file, ...cells]);
    child.on("error", reject);
    child.on("close", (code) => resolve(code ?? -1));
  });

describe("decision log rows", () => {
  it("keeps every row whole when writers append at the same time", async () => {
    const directory = mkdtempSync(join(tmpdir(), "show-me-your-work-"));
    try {
      const file = join(directory, "decisions.tsv");
      // Wide enough that stdio hands the row to the kernel in pieces.
      const wide = "x".repeat(200_000);
      const codes = await Promise.all(
        Array.from({ length: 8 }, (_, index) =>
          append(file, [
            "phase",
            `decision-${index}`,
            wide,
            "evidence",
            "result",
          ])
        )
      );
      expect(codes).toEqual([0, 0, 0, 0, 0, 0, 0, 0]);

      const rows = readFileSync(file, "utf8")
        .split("\n")
        .filter((line) => line !== "" && !line.startsWith("ts\t"))
        .map((line) => line.split("\t"));
      expect(rows.filter((cells) => cells.length !== 6)).toEqual([]);
      expect(rows.map((cells) => cells[2]).sort()).toEqual(
        Array.from({ length: 8 }, (_, index) => `decision-${index}`).sort()
      );
      expect(rows.filter((cells) => cells[3] !== wide)).toEqual([]);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
});
