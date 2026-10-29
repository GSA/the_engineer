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

export function patchWorkspaceTargetOutputSchema(source) {
    const oldBlock = `func (s *Server) addWorkspaceTarget(ctx context.Context, in addWorkspaceTargetInput) (WorkspaceTarget, error) {
\tid, err := workspaceScope(ctx, in.WorkspaceID)
\tif err != nil {
\t\treturn WorkspaceTarget{}, err
\t}
\titem, err := in.Item.itemIdentity()
\tif err != nil {
\t\treturn WorkspaceTarget{}, err
\t}
\treturn s.backend.AddWorkspaceTarget(ctx, id, WorkspaceTargetRequest{Item: item, URL: strings.TrimSpace(in.URL)})
}

func (s *Server) addWorkspaceKataTarget(ctx context.Context, in addWorkspaceKataTargetInput) (WorkspaceTarget, error) {
\tid, err := workspaceScope(ctx, in.WorkspaceID)
\tif err != nil {
\t\treturn WorkspaceTarget{}, err
\t}
\treturn s.backend.AddWorkspaceTarget(ctx, id, WorkspaceTargetRequest{Kata: &WorkspaceKataTarget{DaemonID: in.DaemonID, ProjectUID: in.ProjectUID, IssueUID: in.IssueUID}})
}

func (s *Server) listWorkspaceTargets(ctx context.Context, in workspaceTargetsInput) (WorkspaceTargets, error) {
\tid, err := workspaceScope(ctx, in.WorkspaceID)
\tif err != nil {
\t\treturn WorkspaceTargets{}, err
\t}
\treturn s.backend.ListWorkspaceTargets(ctx, id)
}`;
    assert.ok(
        source.includes(oldBlock),
        "Unexpected tools_workspace_targets.go structure; re-evaluate patchWorkspaceTargetOutputSchema",
    );
    const newBlock = `type workspaceTargetRepoOut struct {
\tProvider                string \`json:"provider"\`
\tPlatformHost            string \`json:"platform_host"\`
\tPlatformRepoID          int64  \`json:"platform_repo_id,omitempty"\`
\tBitbucketRepositoryUUID string \`json:"bitbucket_repository_uuid,omitempty"\`
\tRepoPath                string \`json:"repo_path"\`
\tOwner                   string \`json:"owner"\`
\tName                    string \`json:"name"\`
}

type workspaceTargetOut struct {
\tID          int64                   \`json:"id"\`
\tRepository  *workspaceTargetRepoOut \`json:"repository,omitempty"\`
\tType        string                  \`json:"type"\`
\tNumber      int                     \`json:"number,omitempty"\`
\tURL         string                  \`json:"url,omitempty"\`
\tTitle       string                  \`json:"title"\`
\tState       string                  \`json:"state"\`
\tSource      string                  \`json:"source"\`
\tUnavailable bool                    \`json:"unavailable"\`
\tKata        *WorkspaceKataTarget    \`json:"kata,omitempty"\`
}

type workspaceTargetsOut struct {
\tTargets       []workspaceTargetOut \`json:"targets"\`
\tKataAvailable bool                 \`json:"kata_available"\`
}

func toWorkspaceTargetOut(target WorkspaceTarget) workspaceTargetOut {
\tvar repo *workspaceTargetRepoOut
\tif target.Repository != nil {
\t\tplatformRepoID, repositoryUUID := repositoryKeyFields(target.Repository.Key)
\t\trepo = &workspaceTargetRepoOut{
\t\t\tProvider:                target.Repository.Provider,
\t\t\tPlatformHost:            target.Repository.PlatformHost,
\t\t\tPlatformRepoID:          platformRepoID,
\t\t\tBitbucketRepositoryUUID: repositoryUUID,
\t\t\tRepoPath:                target.Repository.RepoPath,
\t\t\tOwner:                   target.Repository.Owner,
\t\t\tName:                    target.Repository.Name,
\t\t}
\t}
\treturn workspaceTargetOut{
\t\tID:          target.ID,
\t\tRepository:  repo,
\t\tType:        target.Type,
\t\tNumber:      target.Number,
\t\tURL:         target.URL,
\t\tTitle:       target.Title,
\t\tState:       target.State,
\t\tSource:      target.Source,
\t\tUnavailable: target.Unavailable,
\t\tKata:        target.Kata,
\t}
}

func (s *Server) addWorkspaceTarget(ctx context.Context, in addWorkspaceTargetInput) (workspaceTargetOut, error) {
\tid, err := workspaceScope(ctx, in.WorkspaceID)
\tif err != nil {
\t\treturn workspaceTargetOut{}, err
\t}
\titem, err := in.Item.itemIdentity()
\tif err != nil {
\t\treturn workspaceTargetOut{}, err
\t}
\ttarget, err := s.backend.AddWorkspaceTarget(ctx, id, WorkspaceTargetRequest{Item: item, URL: strings.TrimSpace(in.URL)})
\tif err != nil {
\t\treturn workspaceTargetOut{}, err
\t}
\treturn toWorkspaceTargetOut(target), nil
}

func (s *Server) addWorkspaceKataTarget(ctx context.Context, in addWorkspaceKataTargetInput) (workspaceTargetOut, error) {
\tid, err := workspaceScope(ctx, in.WorkspaceID)
\tif err != nil {
\t\treturn workspaceTargetOut{}, err
\t}
\ttarget, err := s.backend.AddWorkspaceTarget(ctx, id, WorkspaceTargetRequest{Kata: &WorkspaceKataTarget{DaemonID: in.DaemonID, ProjectUID: in.ProjectUID, IssueUID: in.IssueUID}})
\tif err != nil {
\t\treturn workspaceTargetOut{}, err
\t}
\treturn toWorkspaceTargetOut(target), nil
}

func (s *Server) listWorkspaceTargets(ctx context.Context, in workspaceTargetsInput) (workspaceTargetsOut, error) {
\tid, err := workspaceScope(ctx, in.WorkspaceID)
\tif err != nil {
\t\treturn workspaceTargetsOut{}, err
\t}
\tout, err := s.backend.ListWorkspaceTargets(ctx, id)
\tif err != nil {
\t\treturn workspaceTargetsOut{}, err
\t}
\ttargets := make([]workspaceTargetOut, 0, len(out.Targets))
\tfor _, target := range out.Targets {
\t\ttargets = append(targets, toWorkspaceTargetOut(target))
\t}
\treturn workspaceTargetsOut{
\t\tTargets:       targets,
\t\tKataAvailable: out.KataAvailable,
\t}, nil
}`;
    return source.replace(oldBlock, newBlock);
}

export function verifyLocalLock(original, derived) {
    const expected = structuredClone(original);
    const actual = structuredClone(derived);
    assert.equal(actual.workspaces.frontend.dependencies[dependency], localDependency);
    assert.deepEqual(actual.packages[localPackage], ["kata@file:../kata", {}]);
    delete expected.workspaces.frontend.dependencies[dependency];
    delete actual.workspaces.frontend.dependencies[dependency];
    delete expected.packages[dependency];
    delete actual.packages[localPackage];
    assert.deepEqual(actual, expected, "Local substitution changed unrelated locked dependencies");
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
    assert.equal(Bun.version, "1.4.0", "Use the pinned Bun through scripts/build.sh");
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
        const kataGoVersion = "v0.18.0";
        const kataGoRevision = "91ee2f9215b3aff0795e66b8ed22e8494b13eadb";
        assert.match(goMod, /^\tgo\.kenn\.io\/kata v0\.18\.0$/m,
            "Re-evaluate the pinned local Kata Go dependency");
        exportSource("kata", kataGoRevision, join(workspace, "kata-go"),
            join(workspace, "kata-go.tar"));
        run("go", ["mod", "edit", `-replace=go.kenn.io/kata@${kataGoVersion}=../kata-go`], forge);
        const localGoMod = `${goMod}\nreplace go.kenn.io/kata ${kataGoVersion} => ../kata-go\n`;
        assert.equal(readFileSync(goModPath, "utf8"), localGoMod,
            "Local substitution changed unrelated Go module requirements");

        const targetsToolPath = join(forge, "internal/mcpserver/tools_workspace_targets.go");
        writeFileSync(
            targetsToolPath,
            patchWorkspaceTargetOutputSchema(readFileSync(targetsToolPath, "utf8")),
        );

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
        run("make", ["build", "-o", "frontend-deps",
            `VERSION=${version}`, `COMMIT=${forgeRevision}`], forge, env);
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
        for (const binary of ["kenn-forge", "kenn-forge-github-app"]) {
            renameSync(join(forge, binary), join(output, binary));
        }
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
