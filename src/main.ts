import { Plugin } from "obsidian";
import deckJson from "../data/deck.json";
import { AudioDownloader } from "./audio-downloader";
import { AudioDownloadModal } from "./audio-download-modal";
import { DeckStore } from "./deck-store";
import { LocalAudio } from "./local-audio";
import { normalizePlaybackRate } from "./playback-speed";
import { DagensOrdSettingTab } from "./settings";
import { DEFAULT_SETTINGS, type DagensOrdSettings, CEFR_LEVELS } from "./types";
import { DagensOrdView, VIEW_TYPE } from "./view";

export default class DagensOrdPlugin extends Plugin {
	settings: DagensOrdSettings = DEFAULT_SETTINGS;
	deckStore = new DeckStore(this.app);
	audio!: LocalAudio;
	audioDownloader!: AudioDownloader;

	async onload(): Promise<void> {
		await this.loadSettings();
		await this.deckStore.loadDeck(JSON.stringify(deckJson));

		const pluginDir = this.manifest.dir || "";
		this.audio = new LocalAudio(this.app, pluginDir);
		this.audioDownloader = new AudioDownloader(this.app, pluginDir);

		this.registerView(VIEW_TYPE, (leaf) => new DagensOrdView(leaf, this));

		this.addRibbonIcon("languages", "Dagens ord", () => {
			void this.activateView();
		});

		this.addCommand({
			id: "open-dagens-ord",
			name: "打开每日丹麦语",
			callback: () => void this.activateView(),
		});

		this.addCommand({
			id: "dagens-ord-today",
			name: "跳转到今日单词",
			callback: () => {
				this.deckStore.goToToday(
					this.settings.dailyWordCount,
					this.settings.dailyCefrLevels,
				);
				void this.activateView();
			},
		});

		this.addCommand({
			id: "dagens-ord-download-audio",
			name: "下载发音音频 / Download pronunciation audio",
			callback: () => this.openAudioDownloadModal(),
		});

		this.addSettingTab(new DagensOrdSettingTab(this.app, this));

		this.app.workspace.onLayoutReady(() => void this.maybePromptAudioDownload());
	}

	openAudioDownloadModal(): void {
		new AudioDownloadModal(this.app, this.audioDownloader, (success) => {
			if (success) {
				this.settings.audioDownloaded = true;
				this.settings.audioPromptDismissed = true;
			} else {
				this.settings.audioPromptDismissed = true;
			}
			void this.saveSettings();
		}).open();
	}

	private async maybePromptAudioDownload(): Promise<void> {
		if (this.settings.audioDownloaded) return;

		if (await this.audioDownloader.hasLocalAudio()) {
			this.settings.audioDownloaded = true;
			await this.saveSettings();
			return;
		}

		if (this.settings.audioPromptDismissed) return;
		this.openAudioDownloadModal();
	}

	onunload(): void {
		this.app.workspace.detachLeavesOfType(VIEW_TYPE);
	}

	async loadSettings(): Promise<void> {
		const saved = (await this.loadData()) as Partial<DagensOrdSettings> | null;
		this.settings = { ...DEFAULT_SETTINGS, ...saved };
		if (!saved?.dailyWordCount || saved.dailyWordCount === 2000) {
			this.settings.dailyWordCount = DEFAULT_SETTINGS.dailyWordCount;
			await this.saveSettings();
		}
		if (!Array.isArray(saved?.dailyCefrLevels) || saved.dailyCefrLevels.length === 0) {
			this.settings.dailyCefrLevels = [...DEFAULT_SETTINGS.dailyCefrLevels];
		} else {
			const valid = new Set<string>(CEFR_LEVELS);
			this.settings.dailyCefrLevels = saved.dailyCefrLevels.filter((level): level is typeof CEFR_LEVELS[number] =>
				valid.has(level),
			);
			if (this.settings.dailyCefrLevels.length === 0) {
				this.settings.dailyCefrLevels = [...DEFAULT_SETTINGS.dailyCefrLevels];
			}
		}
		this.settings.playbackRate = normalizePlaybackRate(this.settings.playbackRate);
	}

	async saveSettings(): Promise<void> {
		await this.saveData(this.settings);
	}

	refreshView(): void {
		const leaves = this.app.workspace.getLeavesOfType(VIEW_TYPE);
		for (const leaf of leaves) {
			const view = leaf.view;
			if (view instanceof DagensOrdView) view.render();
		}
	}

	private async activateView(): Promise<void> {
		const { workspace } = this.app;
		let leaf = workspace.getLeavesOfType(VIEW_TYPE)[0];

		if (!leaf) {
			const rightLeaf = workspace.getRightLeaf(false);
			if (!rightLeaf) return;
			await rightLeaf.setViewState({ type: VIEW_TYPE, active: true });
			leaf = rightLeaf;
		}

		workspace.revealLeaf(leaf);
	}
}
