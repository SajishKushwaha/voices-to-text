import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const binDir = path.join(rootDir, "bin", "piper");
const voicesDir = path.join(rootDir, "voices");
const tmpDir = path.join(rootDir, ".tmp", "piper-install");
const releaseApiUrl = "https://api.github.com/repos/rhasspy/piper/releases/latest";

await fs.mkdir(binDir, { recursive: true });
await fs.mkdir(voicesDir, { recursive: true });
await fs.mkdir(tmpDir, { recursive: true });

await installPiperBinary();
await installVoices();

console.log("Piper TTS is installed locally.");

async function installPiperBinary() {
  const executableName = process.platform === "win32" ? "piper.exe" : "piper";
  const existingBinary = await findFile(binDir, executableName);

  if (existingBinary) {
    if (process.platform !== "win32") {
      await fs.chmod(existingBinary, 0o755);
    }

    console.log(`Piper binary already exists: ${relative(existingBinary)}`);
    await ensureRunnablePiper(existingBinary);
    return;
  }

  const release = await fetchJson(releaseApiUrl);
  const asset = selectReleaseAsset(release.assets ?? []);

  if (!asset) {
    throw new Error(
      `No Piper release asset found for ${process.platform}/${process.arch}. Download it manually from ${release.html_url}.`
    );
  }

  const archivePath = path.join(tmpDir, asset.name);
  console.log(`Downloading ${asset.name}...`);
  await downloadFile(asset.browser_download_url, archivePath);

  console.log("Extracting Piper binary...");
  await extractArchive(archivePath, binDir);

  const extractedBinary = await findFile(
    binDir,
    executableName
  );

  if (!extractedBinary) {
    throw new Error("Piper binary was not found after extraction.");
  }

  if (process.platform !== "win32") {
    await fs.chmod(extractedBinary, 0o755);
  }

  console.log(`Installed Piper binary: ${relative(extractedBinary)}`);
  await ensureRunnablePiper(extractedBinary);
}

async function installVoices() {
  const manifestPath = path.join(voicesDir, "manifest.json");
  const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));

  for (const voice of manifest.voices) {
    await downloadIfMissing(voice.modelUrl, path.join(voicesDir, voice.modelFile));
    await downloadIfMissing(voice.configUrl, path.join(voicesDir, voice.configFile));
  }
}

async function ensureRunnablePiper(binaryPath) {
  if (process.platform !== "darwin") {
    return;
  }

  const fileOutput = execFileSync("file", [binaryPath], {
    encoding: "utf8"
  });
  const expectedArch = process.arch === "arm64" ? "arm64" : "x86_64";

  if (fileOutput.includes(expectedArch)) {
    return;
  }

  console.warn(
    `Piper binary architecture does not match this machine (${process.arch}). Installing Python Piper fallback...`
  );
  await installPythonPiperFallback();
}

async function installPythonPiperFallback() {
  const venvDir = path.join(rootDir, ".venv");
  const pythonBin = path.join(
    venvDir,
    process.platform === "win32" ? "Scripts" : "bin",
    process.platform === "win32" ? "python.exe" : "python"
  );
  const piperBin = path.join(
    venvDir,
    process.platform === "win32" ? "Scripts" : "bin",
    process.platform === "win32" ? "piper.exe" : "piper"
  );

  if (!(await exists(pythonBin))) {
    execFileSync("python3", ["-m", "venv", venvDir], {
      stdio: "inherit"
    });
  }

  if (!(await exists(piperBin))) {
    execFileSync(pythonBin, ["-m", "pip", "install", "piper-tts"], {
      stdio: "inherit"
    });
  }

  console.log(`Installed Piper Python fallback: ${relative(piperBin)}`);
}

function selectReleaseAsset(assets) {
  const matcherGroups = getPlatformMatchers();

  for (const matchers of matcherGroups) {
    const found = assets.find((asset) => {
      const name = asset.name ?? "";
      return (
        /\.(tar\.gz|zip)$/i.test(name) &&
        !/debug|symbols/i.test(name) &&
        matchers.every((matcher) => matcher.test(name))
      );
    });

    if (found) {
      return found;
    }
  }

  return null;
}

function getPlatformMatchers() {
  if (process.platform === "darwin" && process.arch === "arm64") {
    return [[/macos|darwin/i, /aarch64|arm64/i]];
  }

  if (process.platform === "darwin" && process.arch === "x64") {
    return [[/macos|darwin/i, /x64|x86_64|amd64/i]];
  }

  if (process.platform === "linux" && process.arch === "arm64") {
    return [[/linux/i, /aarch64|arm64/i]];
  }

  if (process.platform === "linux" && process.arch === "x64") {
    return [[/linux/i, /x64|x86_64|amd64/i]];
  }

  if (process.platform === "win32" && process.arch === "x64") {
    return [[/windows|win/i, /x64|x86_64|amd64/i]];
  }

  return [[new RegExp(process.platform, "i"), new RegExp(process.arch, "i")]];
}

async function extractArchive(archivePath, destination) {
  if (archivePath.endsWith(".zip")) {
    execFileSync("unzip", ["-oq", archivePath, "-d", destination], {
      stdio: "inherit"
    });
    return;
  }

  execFileSync("tar", ["-xzf", archivePath, "-C", destination], {
    stdio: "inherit"
  });
}

async function downloadIfMissing(url, destination) {
  if (await exists(destination)) {
    console.log(`Voice file already exists: ${relative(destination)}`);
    return;
  }

  console.log(`Downloading ${path.basename(destination)}...`);
  await downloadFile(url, destination);
}

async function downloadFile(url, destination) {
  const response = await fetch(url, {
    headers: {
      "User-Agent": "next-piper-tts-installer"
    }
  });

  if (!response.ok) {
    throw new Error(`Download failed (${response.status}) for ${url}`);
  }

  const buffer = Buffer.from(await response.arrayBuffer());
  await fs.writeFile(destination, buffer);
}

async function fetchJson(url) {
  const response = await fetch(url, {
    headers: {
      Accept: "application/vnd.github+json",
      "User-Agent": "next-piper-tts-installer"
    }
  });

  if (!response.ok) {
    throw new Error(`GitHub release lookup failed (${response.status}).`);
  }

  return response.json();
}

async function findFile(directory, fileName) {
  const entries = await fs.readdir(directory, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);

    if (entry.isFile() && entry.name === fileName) {
      return fullPath;
    }

    if (entry.isDirectory()) {
      const found = await findFile(fullPath, fileName);

      if (found) {
        return found;
      }
    }
  }

  return null;
}

async function exists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

function relative(filePath) {
  return path.relative(rootDir, filePath);
}
