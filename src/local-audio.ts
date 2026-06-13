import { FileSystemAdapter } from "obsidian";
import type { App } from "obsidian";

export interface AudioResult {
	buffer: ArrayBuffer;
	mime: string;
}

export class LocalAudio {
	constructor(
		private app: App,
		private pluginDir: string,
	) {}

	async getAudio(
		cacheKey: string,
		ankiFile?: string | null,
	): Promise<AudioResult> {
		const candidates: { path: string; mime: string }[] = [
			{ path: `${this.pluginDir}/audio/generated/${cacheKey}.ogg`, mime: "audio/ogg" },
			{ path: `${this.pluginDir}/audio/generated/${cacheKey}.wav`, mime: "audio/wav" },
			{ path: `${this.pluginDir}/audio/generated/${cacheKey}.mp3`, mime: "audio/mpeg" },
			{
				path: `${this.app.vault.configDir}/dagens-ord/audio-cache/${cacheKey}.wav`,
				mime: "audio/wav",
			},
		];

		if (ankiFile) {
			candidates.push({
				path: `${this.pluginDir}/audio/anki/${ankiFile}`,
				mime: "audio/mpeg",
			});
		}

		for (const { path, mime } of candidates) {
			const data = await this.readFile(path);
			if (data) return { buffer: data, mime };
		}

		if (cacheKey.startsWith("ex-")) {
			throw new Error(
				"例句音频未生成。请运行: python3 scripts/gemini-browser-batch.py",
			);
		}

		throw new Error("单词音频缺失。请重新运行 npm run extract");
	}

	private async readFile(path: string): Promise<ArrayBuffer | null> {
		const adapter = this.app.vault.adapter;
		if (!(await adapter.exists(path))) return null;
		try {
			return await adapter.readBinary(path);
		} catch {
			return null;
		}
	}
}
