import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
    copyFileSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const dependency = "@kenn-io/kata-ui";
const localPackage = `kenn-forge-frontend/${dependency}`;
const localDependency = "file:../../kata";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function verifyLocalLock(original, derived) {
    const expected = structuredClone(original);
    const actual = structuredClone(derived);
    assert.equal(actual.workspaces.frontend.dependencies[dependency], localDependency);
    const [localSpec, localMetadata] = actual.packages[localPackage];
    assert.equal(localSpec, "kata@file:../kata");
    assert.deepEqual(Object.keys(localMetadata).filter((key) => key !== "devDependencies"), []);
    delete expected.workspaces.frontend.dependencies[dependency];
    delete actual.workspaces.frontend.dependencies[dependency];
    delete expected.packages[dependency];
    // A file: dependency locks its own devDependencies as a nested subtree.
    for (const key of Object.keys(actual.packages)) {
        if (key === localPackage || key.startsWith(`${localPackage}/`)) {
            delete actual.packages[key];
        }
    }
    assert.deepEqual(actual, expected, "Local substitution changed unrelated locked dependencies");
}

// Forge's single tagged go.kenn.io/kata requirement, substituted from local source.
export function kataGoRequirement(goMod) {
    assert.doesNotMatch(goMod, /^\s*replace\b.*go\.kenn\.io\/kata\b/m,
        "Forge already replaces go.kenn.io/kata; re-evaluate the local Kata build");
    const versions = [...goMod.matchAll(/^\s*(?:require\s+)?go\.kenn\.io\/kata (\S+)/gm)]
        .map((match) => match[1]);
    assert.equal(versions.length, 1, "Expected exactly one go.kenn.io/kata requirement");
    assert.match(versions[0], /^v\d+\.\d+\.\d+$/,
        "Forge requires an untagged go.kenn.io/kata; re-evaluate the local Kata build");
    return versions[0];
}

function git(project, ...args) {
    return execFileSync("git", ["-C", join(root, project), ...args], {
        encoding: "utf8",
    }).trim();
}

function run(command, args, cwd, env = process.env) {
    execFileSync(command, args, { cwd, env, stdio: "inherit" });
}

function exportSource(project, revision, destination, archive) {
    mkdirSync(destination);
    git(project, "archive", "--format=tar", `--output=${archive}`, revision);
    run("tar", ["-xf", archive, "-C", destination], root);
}

function main() {
    assert.equal(Bun.version, "1.4.4", "Use the pinned Bun through scripts/build.sh");
    assert.equal(git("forge", "status", "--porcelain", "--untracked-files=no"), "",
        "Forge has tracked changes; refusing to silently omit them from the export");
    const forgeRevision = git("forge", "rev-parse", "HEAD");
    const version = `${git("forge", "describe", "--tags", "--always")}-local-kata`;
    const parent = join(root, ".local", "builds");
    mkdirSync(parent, { recursive: true });
    const workspace = mkdtempSync(join(parent, "forge-local-kata-"));
    const forge = join(workspace, "forge");
    const kata = join(workspace, "kata");
    let completed = false;
    console.log(`Temporary build workspace: ${workspace}`);
    try {
        exportSource("forge", forgeRevision, forge, join(workspace, "forge.tar"));
        // Keep formatters from inheriting the parent's .local/ ignore rule.
        run("git", ["init", "--quiet", "--template="], forge);
        const original = Bun.JSONC.parse(readFileSync(join(forge, "bun.lock"), "utf8"));
        const match = /^kata@github:kenn-io\/kata#([0-9a-f]{7,40})$/.exec(
            original.packages[dependency][0],
        );
        assert.ok(match, "Unexpected Kata dependency format; re-evaluate the temporary build");
        const kataRevision = git("kata", "rev-parse", `${match[1]}^{commit}`);
        exportSource("kata", kataRevision, kata, join(workspace, "kata.tar"));
        // Bun cannot reread a file-dependency lock entry for a nameless workspace root.
        const kataManifestPath = join(kata, "package.json");
        const kataManifest = JSON.parse(readFileSync(kataManifestPath, "utf8"));
        assert.equal(kataManifest.name, undefined, "Re-evaluate the local Kata package metadata");
        kataManifest.name = "kata";
        writeFileSync(kataManifestPath, `${JSON.stringify(kataManifest, null, 2)}\n`);

        const goModPath = join(forge, "go.mod");
        const goMod = readFileSync(goModPath, "utf8");
        const goSumPath = join(forge, "go.sum");
        const goSum = readFileSync(goSumPath);
        const kataGoVersion = kataGoRequirement(goMod);
        const kataGoRevision = git("kata", "rev-parse", `refs/tags/${kataGoVersion}^{commit}`);
        // Substitute only a release already contained in the pinned Kata submodule.
        execFileSync("git", ["-C", join(root, "kata"), "merge-base", "--is-ancestor",
            kataGoRevision, git("kata", "rev-parse", "HEAD")]);
        exportSource("kata", kataGoRevision, join(workspace, "kata-go"),
            join(workspace, "kata-go.tar"));
        run("go", ["mod", "edit", `-replace=go.kenn.io/kata@${kataGoVersion}=../kata-go`], forge);
        const localGoMod = `${goMod}\nreplace go.kenn.io/kata ${kataGoVersion} => ../kata-go\n`;
        assert.equal(readFileSync(goModPath, "utf8"), localGoMod,
            "Local substitution changed unrelated Go module requirements");

        const manifestPath = join(forge, "frontend", "package.json");
        const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
        assert.equal(manifest.dependencies[dependency],
            original.workspaces.frontend.dependencies[dependency]);
        manifest.dependencies[dependency] = localDependency;
        writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);

        run("bun", ["install", "--lockfile-only", "--ignore-scripts"], forge);
        const lockPath = join(forge, "bun.lock");
        verifyLocalLock(original, Bun.JSONC.parse(readFileSync(lockPath, "utf8")));
        const lock = readFileSync(lockPath);
        run("bun", ["install", "--frozen-lockfile"], forge);
        assert.deepEqual(readFileSync(lockPath), lock, "Frozen install modified the derived lockfile");
        run("diff", ["-qr", join(kata, "packages/kata-ui/src"),
            join(forge, "frontend/node_modules/@kenn-io/kata-ui/packages/kata-ui/src")], forge);

        // The scratch repository has no source history; pass the real metadata explicitly.
        const env = {
            ...process.env,
            GOFLAGS: `${process.env.GOFLAGS ?? ""} -buildvcs=false -mod=readonly`,
        };
        // An empty PostHog key compiles Forge without its telemetry destination.
        run("make", ["build", "-o", "frontend-deps",
            `VERSION=${version}`, `COMMIT=${forgeRevision}`, "POSTHOG_PROJECT_KEY="], forge, env);
        assert.equal(readFileSync(goModPath, "utf8"), localGoMod, "Build modified go.mod");
        assert.deepEqual(readFileSync(goSumPath), goSum, "Build modified go.sum");

        const output = join(root, ".local", "forge-local-kata");
        mkdirSync(output, { recursive: true });
        copyFileSync(lockPath, join(output, "bun.lock"));
        copyFileSync(goModPath, join(output, "go.mod"));
        writeFileSync(join(output, "build.json"), `${JSON.stringify({
            variant: "temporary-local-kata",
            forge_revision: forgeRevision,
            kata_ui_revision: kataRevision,
            kata_go_revision: kataGoRevision,
            kata_go_version: kataGoVersion,
            version,
            lock_sha256: createHash("sha256").update(lock).digest("hex"),
        }, null, 2)}\n`);
        renameSync(join(forge, "kenn-forge"), join(output, "kenn-forge"));
        // Forge now ships GitHub App setup as `kenn-forge github-app`.
        rmSync(join(output, "kenn-forge-github-app"), { force: true });
        completed = true;
        console.log(`Built ${join(output, "kenn-forge")}`);
    } finally {
        if (completed) {
            rmSync(workspace, { recursive: true });
        } else {
            console.error(`Build failed; diagnostic workspace retained at ${workspace}`);
        }
    }
}

if (import.meta.main) main();
