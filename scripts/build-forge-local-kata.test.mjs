import { test, expect } from "bun:test";
import { readFileSync } from "node:fs";
import { kataGoRequirement, verifyLocalLock } from "./build-forge-local-kata.mjs";

function locks() {
    const original = Bun.JSONC.parse(readFileSync(
        new URL("../forge/bun.lock", import.meta.url), "utf8",
    ));
    const derived = structuredClone(original);
    derived.workspaces.frontend.dependencies["@kenn-io/kata-ui"] = "file:../../kata";
    delete derived.packages["@kenn-io/kata-ui"];
    derived.packages["kenn-forge-frontend/@kenn-io/kata-ui"] = ["kata@file:../kata", {}];
    return { original, derived };
}

test("permits only the explicit local Kata substitution without mutating inputs", () => {
    const { original, derived } = locks();
    const before = structuredClone({ original, derived });
    verifyLocalLock(original, derived);
    expect({ original, derived }).toEqual(before);
});

test("permits only the local Kata package's own devDependency subtree", () => {
    const { original, derived } = locks();
    const local = "kenn-forge-frontend/@kenn-io/kata-ui";
    derived.packages[local] = ["kata@file:../kata", { devDependencies: { "vite-plus": "1.2.0" } }];
    derived.packages[`${local}/vite-plus`] = ["vite-plus@1.2.0", {}, "sha512-dev"];
    verifyLocalLock(original, derived);
    derived.packages[local] = ["kata@file:../kata", { dependencies: { "vite-plus": "1.2.0" } }];
    expect(() => verifyLocalLock(original, derived)).toThrow();
});

test("rejects unrelated package integrity or version drift", () => {
    const { original, derived } = locks();
    derived.packages["@babel/runtime"][0] = "@babel/runtime@0.0.0";
    expect(() => verifyLocalLock(original, derived)).toThrow();
    derived.packages["@babel/runtime"] = [...original.packages["@babel/runtime"]];
    derived.packages["@babel/runtime"][3] = "sha512-changed";
    expect(() => verifyLocalLock(original, derived)).toThrow();
});

test("rejects removal of an unrelated package", () => {
    const { original, derived } = locks();
    delete derived.packages["@babel/runtime"];
    expect(() => verifyLocalLock(original, derived)).toThrow();
});

test("rejects a different local path or the original remote archive", () => {
    const { original, derived } = locks();
    derived.packages["kenn-forge-frontend/@kenn-io/kata-ui"] = original.packages["@kenn-io/kata-ui"];
    expect(() => verifyLocalLock(original, derived)).toThrow();
    derived.packages["kenn-forge-frontend/@kenn-io/kata-ui"] = ["kata@file:../other-kata", {}];
    expect(() => verifyLocalLock(original, derived)).toThrow();
});

test("rejects retaining the remote Kata package alongside the local replacement", () => {
    const { original, derived } = locks();
    derived.packages["@kenn-io/kata-ui"] = original.packages["@kenn-io/kata-ui"];
    expect(() => verifyLocalLock(original, derived)).toThrow();
});

test("derives the tagged Kata Go requirement from Forge's go.mod", () => {
    const goMod = readFileSync(new URL("../forge/go.mod", import.meta.url), "utf8");
    expect(kataGoRequirement(goMod)).toMatch(/^v\d+\.\d+\.\d+$/);
    expect(kataGoRequirement("module m\n\nrequire go.kenn.io/kata v1.2.3\n")).toBe("v1.2.3");
});

test("rejects pseudo-versions, duplicates and existing Kata replacements", () => {
    const require = (version) => `module m\n\nrequire (\n\tgo.kenn.io/kata ${version}\n)\n`;
    expect(() => kataGoRequirement(require("v0.21.1-0.20260101000000-abcdef123456"))).toThrow();
    expect(() => kataGoRequirement("module m\n")).toThrow();
    expect(() => kataGoRequirement(`${require("v0.21.0")}require go.kenn.io/kata v0.22.0\n`)).toThrow();
    expect(() => kataGoRequirement(`${require("v0.21.0")}replace go.kenn.io/kata => ../kata\n`)).toThrow();
});
