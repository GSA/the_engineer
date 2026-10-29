import { test, expect } from "bun:test";
import { readFileSync } from "node:fs";
import { patchWorkspaceTargetOutputSchema, verifyLocalLock } from "./build-forge-local-kata.mjs";

test("patches tools_workspace_targets.go output types to expose repository key fields in MCP schema", () => {
    const source = readFileSync(
        new URL("../forge/internal/mcpserver/tools_workspace_targets.go", import.meta.url),
        "utf8",
    );
    const patched = patchWorkspaceTargetOutputSchema(source);
    expect(patched).toContain("type workspaceTargetRepoOut struct");
    expect(patched).toContain('PlatformRepoID          int64  `json:"platform_repo_id,omitempty"`');
    expect(patched).toContain("func toWorkspaceTargetOut(target WorkspaceTarget) workspaceTargetOut");
});

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
