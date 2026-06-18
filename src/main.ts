import { Plugin } from "obsidian";
import * as deckJson from "../data/deck.json";
import { AudioDownloader } from "./audio-downloader";
import { AudioDownloadModal } from "./audio-download-modal";
import { DeckStore } from "./deck-store";
import { FloatingCardController } from "./floating-card";
import { LocalAudio } from "./local-audio";
import { normalizePlaybackRate } from "./playback-speed";
import { DagensOrdSettingTab } from "./settings";
import {
	DEFAULT_SETTINGS,
	type CardDisplayMode,
	type DagensOrdSettings,
	CEFR_LEVELS,
} from "./types";
import { DagensOrdView, VIEW_TYPE } from "./view";

export default class DagensOrdPlugin extends Plugin {
	settings: DagensOrdSettings = DEFAULT_SETTINGS;
	deckStore = new DeckStore(this.app);
	audio!: LocalAudio;
	audioDownloader!: AudioDownloader;
	private audioModalOpen = false;
	private floatingCard: FloatingCardController | null = null;

	async onload(): Promise<void> {
		await this.loadSettings();
		await this.deckStore.loadDeck(JSON.stringify(deckJson));

		const pluginDir = this.manifest.dir || "";
		this.audio = new LocalAudio(this.app, pluginDir);
		this.audioDownloader = new AudioDownloader(this.app, pluginDir);

		this.registerView(VIEW_TYPE, (leaf) => new DagensOrdView(leaf, this));

		this.addRibbonIcon("languages", "Dagens ord", () => {
			void this.openWithAudioCheck();
		});

		this.addCommand({
			id: "open",
			name: "打开每日丹麦语",
			callback: () => void this.openWithAudioCheck(),
		});

		this.addCommand({
			id: "today",
			name: "跳转到今日单词",
			callback: () => {
				this.deckStore.goToToday(
					this.settings.dailyWordCount,
					this.settings.dailyCefrLevels,
				);
				void this.openCurrentDisplay();
			},
		});

		this.addCommand({
			id: "download-audio",
			name: "下载发音音频 / Download pronunciation audio",
			callback: () => this.openAudioDownloadModal(),
		});

		this.addSettingTab(new DagensOrdSettingTab(this.app, this));
		if (this.settings.cardDisplayMode === "floating") {
			await this.syncCardDisplayMode();
		}
	}

	onunload(): void {
		this.floatingCard?.destroy();
		this.floatingCard = null;
	}

	openAudioDownloadModal(): void {
		if (this.audioModalOpen) return;
		this.audioModalOpen = true;
		new AudioDownloadModal(this.app, this.audioDownloader, (success) => {
			this.audioModalOpen = false;
			this.settings.audioDownloaded = success;
			void this.saveSettings();
		}).open();
	}

	/** Open the view; run a self-check first and prompt if local audio is missing. */
	private async openWithAudioCheck(): Promise<void> {
		const ok = await this.runAudioSelfCheck();
		if (!ok) {
			this.openAudioDownloadModal();
		}
		await this.openCurrentDisplay();
	}

	/**
	 * Returns true when the local audio is complete (no missing files vs. the
	 * remote manifest). Falls back to a local-presence check when offline.
	 */
	private async runAudioSelfCheck(): Promise<boolean> {
		let ok: boolean;
		try {
			const missing = await this.audioDownloader.getMissingFiles();
			ok = missing.length === 0;
		} catch {
			// Could not reach GitHub: don't nag if there is already local audio.
			ok = await this.audioDownloader.hasLocalAudio();
		}
		if (this.settings.audioDownloaded !== ok) {
			this.settings.audioDownloaded = ok;
			await this.saveSettings();
		}
		return ok;
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
		if (this.settings.cardDisplayMode !== "sidebar" && this.settings.cardDisplayMode !== "floating") {
			this.settings.cardDisplayMode = DEFAULT_SETTINGS.cardDisplayMode;
		}
		if (
			!this.settings.floatingCardPosition
			|| typeof this.settings.floatingCardPosition.left !== "number"
			|| typeof this.settings.floatingCardPosition.top !== "number"
		) {
			this.settings.floatingCardPosition = {
				...DEFAULT_SETTINGS.floatingCardPosition,
			};
		}
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
		this.refreshFloatingCard();
	}

	async setCardDisplayMode(mode: CardDisplayMode): Promise<void> {
		this.settings.cardDisplayMode = mode;
		this.settings.floatingCardHidden = false;
		await this.saveSettings();
		await this.syncCardDisplayMode();
	}

	async syncCardDisplayMode(): Promise<void> {
		if (this.settings.cardDisplayMode === "floating") {
			this.closeSidebarViews();
			this.ensureFloatingCard().sync();
			return;
		}

		this.floatingCard?.destroy();
		this.floatingCard = null;
		await this.activateView();
	}

	refreshFloatingCard(): void {
		if (this.settings.cardDisplayMode !== "floating") return;
		this.ensureFloatingCard().sync();
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

		await workspace.revealLeaf(leaf);
	}

	private async openCurrentDisplay(): Promise<void> {
		if (this.settings.cardDisplayMode === "floating") {
			this.closeSidebarViews();
			this.ensureFloatingCard().sync();
			return;
		}

		await this.activateView();
	}

	private ensureFloatingCard(): FloatingCardController {
		if (!this.floatingCard) {
			this.floatingCard = new FloatingCardController(this);
		}
		return this.floatingCard;
	}

	private closeSidebarViews(): void {
		const leaves = this.app.workspace.getLeavesOfType(VIEW_TYPE);
		for (const leaf of leaves) {
			void leaf.detach();
		}
	}
}
