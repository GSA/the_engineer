import { expect, test } from "bun:test";
import { extractJson } from "./json-extract.ts";

test("parses a bare JSON document", () => {
    expect(extractJson('  {"a": 1}\n')).toEqual({ a: 1 });
});

test("reads a fenced json block", () => {
    expect(extractJson('Here:\n```json\n{"a": [1, 2]}\n```\ndone')).toEqual({ a: [1, 2] });
});

test("returns the first object when prose wraps several unrelated ones", () => {
    expect(extractJson('Result {"a": 1} and then {"b": 2} later.')).toEqual({ a: 1 });
});

test("skips braces in prose that are not JSON", () => {
    expect(extractJson('Use {curly} braces, then {"a": "x}y"} ok')).toEqual({ a: "x}y" });
});

test("keeps an array of objects whole", () => {
    expect(extractJson('Output: [{"a": 1}, {"b": 2}] end')).toEqual([{ a: 1 }, { b: 2 }]);
});

test("returns null when no JSON value exists", () => {
    expect(extractJson("no json {here")).toBeNull();
    expect(extractJson('{"a": ')).toBeNull();
});
