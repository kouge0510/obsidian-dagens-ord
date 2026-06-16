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
				"The pronunciation audio for this plugin has not been downloaded to your device yet. " +
				"Would you like to download it now from GitHub? This may take a while and requires an internet connection.",
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
			if (result.failed > 0) {
				new Notice(
					`Audio download finished with ${result.failed} failed file(s). You can re-run the download to retry.`,
				);
			} else {
				new Notice("Audio download complete.");
			}
			this.onComplete(true);
			this.close();
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
}
