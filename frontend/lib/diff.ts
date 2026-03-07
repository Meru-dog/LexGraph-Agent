import type { DiffLine } from "./types";

// Line-by-line diff algorithm as specified in the RDD (§2.5)
export function diffLines(original: string, reviewed: string): DiffLine[] {
  const oLines = original.split("\n");
  const rLines = reviewed.split("\n");
  const result: DiffLine[] = [];
  let i = 0;
  let j = 0;

  while (i < oLines.length || j < rLines.length) {
    const o = i < oLines.length ? oLines[i] : null;
    const r = j < rLines.length ? rLines[j] : null;

    if (o === r) {
      result.push({ type: "same", text: o! });
      i++;
      j++;
    } else if (o !== null && (r === null || !rLines.slice(j).includes(o))) {
      result.push({ type: "removed", text: o });
      i++;
    } else if (r !== null && (o === null || !oLines.slice(i).includes(r))) {
      result.push({ type: "added", text: r });
      j++;
    } else {
      result.push({ type: "removed", text: o! });
      result.push({ type: "added", text: r! });
      i++;
      j++;
    }
  }

  return result;
}

export function countDiffStats(diff: DiffLine[]): { added: number; removed: number } {
  return {
    added: diff.filter((l) => l.type === "added").length,
    removed: diff.filter((l) => l.type === "removed").length,
  };
}
