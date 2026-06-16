import { App, Modal, Notice, Setting } from "obsidian";
import {
	AudioDownloadCancelled,
	AudioDownloader,
	type DownloadProgress,
} from "./audio-downloader";

export class AudioDownloadModal extends Modal {
	private downloader: AudioDownloader;
	private downloading = false;
	private onComplete: (success: boolean) => void;

	constructor(
		app: App,
		downloader: AudioDownloader,
		onComplete: (success: boolean) => void,
	) {
		super(app);
		this.downloader = downloader;
		this.onComplete = onComplete;
	}

	onOpen(): void {
		this.renderPrompt();
	}

	onClose(): void {
		if (this.downloading) this.downloader.cancel();
		this.contentEl.empty();
	}

	private renderPrompt(): void {
		const { contentEl } = this;
		contentEl.empty();

		new Setting(contentEl).setName("Download pronunciation audio").setHeading();
		contentEl.createEl("p", {
			text:
				"Some pronunciation audio files are missing on your device. " +
				"Would you like to download the missing files now from GitHub? " +
				"This may take a while and requires an internet connection.",
		});

		const buttons = contentEl.createDiv({ cls: "do-modal-buttons" });

		const laterBtn = buttons.createEl("button", { text: "Not now" });
		laterBtn.addEventListener("click", () => {
			this.onComplete(false);
			this.close();
		});

		const downloadBtn = buttons.createEl("button", {
			text: "Download",
			cls: "mod-cta",
		});
		downloadBtn.addEventListener("click", () => void this.startDownload());
	}

	private async startDownload(): Promise<void> {
		const { contentEl } = this;
		contentEl.empty();
		this.downloading = true;

		new Setting(contentEl).setName("Downloading audio…").setHeading();

		const status = contentEl.createEl("p", {
			text: "Fetching file list from GitHub…",
		});

		const barOuter = contentEl.createDiv({ cls: "do-progress-track" });
		const barInner = barOuter.createDiv({ cls: "do-progress-fill" });

		const detail = contentEl.createEl("p", { cls: "setting-item-description" });

		const buttons = contentEl.createDiv({ cls: "do-modal-buttons" });
		const cancelBtn = buttons.createEl("button", { text: "Cancel" });
		cancelBtn.addEventListener("click", () => {
			this.downloader.cancel();
			cancelBtn.disabled = true;
			cancelBtn.setText("Cancelling…");
		});

		const onProgress = (p: DownloadProgress): void => {
			const pct = p.total > 0 ? Math.round((p.completed / p.total) * 100) : 0;
			barInner.setCssStyles({ width: `${pct}%` });
			status.setText(`Downloading audio… ${p.completed} / ${p.total} (${pct}%)`);
			const failedText = p.failed > 0 ? ` • ${p.failed} failed` : "";
			detail.setText(`${p.currentFile}${failedText}`);
		};

		try {
			const result = await this.downloader.downloadAll(onProgress);
			this.downloading = false;
			barInner.setCssStyles({ width: "100%" });
			this.onComplete(result.failed === 0);
			this.renderComplete(result);
		} catch (err) {
			this.downloading = false;
			if (err instanceof AudioDownloadCancelled) {
				new Notice("Audio download cancelled.");
				this.onComplete(false);
				this.close();
				return;
			}
			const msg = err instanceof Error ? err.message : String(err);
			status.setText(`Download failed: ${msg}`);
			cancelBtn.setText("Close");
			cancelBtn.disabled = false;
			cancelBtn.onclick = () => {
				this.onComplete(false);
				this.close();
			};
		}
	}

	private renderComplete(result: DownloadProgress): void {
		const { contentEl } = this;
		contentEl.empty();

		const ok = result.failed === 0;
		const downloaded = Math.max(0, result.completed - result.skipped - result.failed);

		const header = contentEl.createDiv({ cls: "do-complete-header" });
		const badge = header.createDiv({
			cls: ok ? "do-complete-badge" : "do-complete-badge is-error",
			text: ok ? "✓" : "!",
		});
		badge.setAttr("aria-hidden", "true");
		new Setting(header)
			.setName(ok ? "Audio download complete" : "Download finished with errors")
			.setHeading();

		contentEl.createDiv({ cls: "do-complete-bar" });

		const list = contentEl.createEl("ul", { cls: "do-result-list" });
		list.createEl("li", { text: `Total audio files: ${result.total}` });
		list.createEl("li", { text: `Newly downloaded: ${downloaded}` });
		list.createEl("li", { text: `Already present (skipped): ${result.skipped}` });
		if (result.failed > 0) {
			list.createEl("li", { cls: "do-result-failed", text: `Failed: ${result.failed}` });
		}

		contentEl.createEl("p", {
			cls: "setting-item-description",
			text: ok
				? "All pronunciation audio is now available on your device."
				: "Some files could not be downloaded. You can run the download again to retry the failed files.",
		});

		const buttons = contentEl.createDiv({ cls: "do-modal-buttons" });

		if (result.failed > 0) {
			const retryBtn = buttons.createEl("button", { text: "Retry failed" });
			retryBtn.addEventListener("click", () => void this.startDownload());
		}

		const doneBtn = buttons.createEl("button", { text: "Done", cls: "mod-cta" });
		doneBtn.addEventListener("click", () => this.close());

		new Notice(
			ok
				? "Audio download complete."
				: `Audio download finished with ${result.failed} failed file(s).`,
		);
	}
}
