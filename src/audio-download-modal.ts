import { App, Modal, Notice } from "obsidian";
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

		contentEl.createEl("h2", { text: "Download pronunciation audio" });
		contentEl.createEl("p", {
			text:
				"Some pronunciation audio files are missing on your device. " +
				"Would you like to download the missing files now from GitHub? " +
				"This may take a while and requires an internet connection.",
		});

		const buttons = contentEl.createDiv({ cls: "do-modal-buttons" });
		buttons.style.display = "flex";
		buttons.style.justifyContent = "flex-end";
		buttons.style.gap = "8px";
		buttons.style.marginTop = "16px";

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

		contentEl.createEl("h2", { text: "Downloading audio…" });

		const status = contentEl.createEl("p", {
			text: "Fetching file list from GitHub…",
		});

		const barOuter = contentEl.createDiv();
		barOuter.style.width = "100%";
		barOuter.style.height = "10px";
		barOuter.style.borderRadius = "5px";
		barOuter.style.background = "var(--background-modifier-border)";
		barOuter.style.overflow = "hidden";
		barOuter.style.marginTop = "12px";

		const barInner = barOuter.createDiv();
		barInner.style.height = "100%";
		barInner.style.width = "0%";
		barInner.style.background = "var(--interactive-accent)";
		barInner.style.transition = "width 0.1s linear";

		const detail = contentEl.createEl("p", {
			cls: "setting-item-description",
			text: "",
		});

		const buttons = contentEl.createDiv();
		buttons.style.display = "flex";
		buttons.style.justifyContent = "flex-end";
		buttons.style.marginTop = "16px";
		const cancelBtn = buttons.createEl("button", { text: "Cancel" });
		cancelBtn.addEventListener("click", () => {
			this.downloader.cancel();
			cancelBtn.disabled = true;
			cancelBtn.setText("Cancelling…");
		});

		const onProgress = (p: DownloadProgress): void => {
			const pct = p.total > 0 ? Math.round((p.completed / p.total) * 100) : 0;
			barInner.style.width = `${pct}%`;
			status.setText(`Downloading audio… ${p.completed} / ${p.total} (${pct}%)`);
			const failedText = p.failed > 0 ? ` • ${p.failed} failed` : "";
			detail.setText(`${p.currentFile}${failedText}`);
		};

		try {
			const result = await this.downloader.downloadAll(onProgress);
			this.downloading = false;
			barInner.style.width = "100%";
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

		const header = contentEl.createDiv();
		header.style.display = "flex";
		header.style.alignItems = "center";
		header.style.gap = "10px";

		const badge = header.createDiv();
		badge.style.width = "32px";
		badge.style.height = "32px";
		badge.style.borderRadius = "50%";
		badge.style.display = "flex";
		badge.style.alignItems = "center";
		badge.style.justifyContent = "center";
		badge.style.flexShrink = "0";
		badge.style.color = "var(--text-on-accent)";
		badge.style.background = ok
			? "var(--interactive-accent)"
			: "var(--background-modifier-error)";
		badge.setText(ok ? "✓" : "!");
		badge.style.fontWeight = "bold";

		header.createEl("h2", {
			text: ok ? "Audio download complete" : "Download finished with errors",
		});

		const bar = contentEl.createDiv();
		bar.style.width = "100%";
		bar.style.height = "10px";
		bar.style.borderRadius = "5px";
		bar.style.marginTop = "12px";
		bar.style.background = "var(--interactive-accent)";

		const list = contentEl.createEl("ul");
		list.style.marginTop = "14px";
		list.style.lineHeight = "1.7";
		list.createEl("li", { text: `Total audio files: ${result.total}` });
		list.createEl("li", { text: `Newly downloaded: ${downloaded}` });
		list.createEl("li", { text: `Already present (skipped): ${result.skipped}` });
		if (result.failed > 0) {
			const failed = list.createEl("li", { text: `Failed: ${result.failed}` });
			failed.style.color = "var(--text-error)";
		}

		contentEl.createEl("p", {
			cls: "setting-item-description",
			text: ok
				? "All pronunciation audio is now available on your device."
				: "Some files could not be downloaded. You can run the download again to retry the failed files.",
		});

		const buttons = contentEl.createDiv();
		buttons.style.display = "flex";
		buttons.style.justifyContent = "flex-end";
		buttons.style.gap = "8px";
		buttons.style.marginTop = "16px";

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
