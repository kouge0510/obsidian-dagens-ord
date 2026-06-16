import { App, normalizePath, requestUrl } from "obsidian";

const REPO = "kouge0510/obsidian-dagens-ord";
const BRANCH = "main";
const TREE_URL = `https://api.github.com/repos/${REPO}/git/trees/${BRANCH}?recursive=1`;
const RAW_BASE = `https://raw.githubusercontent.com/${REPO}/${BRANCH}/`;

export interface DownloadProgress {
	total: number;
	completed: number;
	skipped: number;
	failed: number;
	currentFile: string;
}

interface GitTreeNode {
	path: string;
	type: string;
}

interface GitTreeResponse {
	tree: GitTreeNode[];
	truncated?: boolean;
}

export class AudioDownloadCancelled extends Error {
	constructor() {
		super("Download cancelled");
		this.name = "AudioDownloadCancelled";
	}
}

export class AudioDownloader {
	private cancelled = false;

	constructor(
		private app: App,
		private pluginDir: string,
	) {}

	cancel(): void {
		this.cancelled = true;
	}

	resetCancel(): void {
		this.cancelled = false;
	}

	/** Check whether the local audio folder already holds files. */
	async hasLocalAudio(): Promise<boolean> {
		const adapter = this.app.vault.adapter;
		for (const sub of ["audio/anki", "audio/generated"]) {
			const dir = normalizePath(`${this.pluginDir}/${sub}`);
			if (!(await adapter.exists(dir))) continue;
			try {
				const listed = await adapter.list(dir);
				if (listed.files.length > 0) return true;
			} catch {
				// ignore and keep checking
			}
		}
		return false;
	}

	/** Fetch the list of remote audio file paths (relative to repo root). */
	async listRemoteAudioFiles(): Promise<string[]> {
		const res = await requestUrl({
			url: TREE_URL,
			headers: { Accept: "application/vnd.github+json" },
		});
		const data = res.json as GitTreeResponse;
		if (!data || !Array.isArray(data.tree)) {
			throw new Error("Unexpected response from GitHub API");
		}
		return data.tree
			.filter((node) => node.type === "blob" && node.path.startsWith("audio/"))
			.map((node) => node.path);
	}

	/**
	 * Download all remote audio files that are missing locally.
	 * Calls onProgress after each file. Throws AudioDownloadCancelled if cancelled.
	 */
	async downloadAll(
		onProgress: (progress: DownloadProgress) => void,
	): Promise<DownloadProgress> {
		this.cancelled = false;
		const files = await this.listRemoteAudioFiles();

		const progress: DownloadProgress = {
			total: files.length,
			completed: 0,
			skipped: 0,
			failed: 0,
			currentFile: "",
		};
		onProgress({ ...progress });

		const adapter = this.app.vault.adapter;

		for (const path of files) {
			if (this.cancelled) throw new AudioDownloadCancelled();

			progress.currentFile = path;
			const localPath = normalizePath(`${this.pluginDir}/${path}`);

			if (await adapter.exists(localPath)) {
				progress.skipped += 1;
				progress.completed += 1;
				onProgress({ ...progress });
				continue;
			}

			try {
				await this.ensureDir(localPath.substring(0, localPath.lastIndexOf("/")));
				const url = RAW_BASE + path.split("/").map(encodeURIComponent).join("/");
				const res = await requestUrl({ url });
				await adapter.writeBinary(localPath, res.arrayBuffer);
			} catch {
				progress.failed += 1;
			}

			progress.completed += 1;
			onProgress({ ...progress });
		}

		return progress;
	}

	private async ensureDir(dir: string): Promise<void> {
		const adapter = this.app.vault.adapter;
		const parts = dir.split("/");
		let current = "";
		for (const part of parts) {
			current = current ? `${current}/${part}` : part;
			if (!current) continue;
			if (!(await adapter.exists(current))) {
				try {
					await adapter.mkdir(current);
				} catch {
					// directory may have been created concurrently
				}
			}
		}
	}
}
