import { App, Notice, PluginSettingTab, Setting } from "obsidian";
import type DagensOrdPlugin from "./main";
import { CEFR_LEVELS, type CefrLevel } from "./types";

export class DagensOrdSettingTab extends PluginSettingTab {
	constructor(app: App, private plugin: DagensOrdPlugin) {
		super(app, plugin);
	}

	display(): void {
		this.refresh();
	}

	private refresh(): void {
		const { containerEl } = this;
		containerEl.empty();

		new Setting(containerEl).setName("General").setHeading();

		containerEl.createEl("p", {
			cls: "setting-item-description",
			text: "Word audio comes from the built-in Anki deck. Example audio is generated locally via edge-tts (no API key required).",
		});

		new Setting(containerEl)
			.setName("Daily word pool size")
			.setDesc("Within selected CEFR levels, take the top N words by frequency (default 4442, full deck)")
			.addText((text) =>
				text
					.setPlaceholder("4442")
					.setValue(String(this.plugin.settings.dailyWordCount))
					.onChange(async (value) => {
						const n = parseInt(value, 10);
						if (!isNaN(n) && n > 0) {
							this.plugin.settings.dailyWordCount = n;
							await this.plugin.saveSettings();
							this.plugin.deckStore.clampCurrentIndex(
								this.plugin.settings.dailyWordCount,
								this.plugin.settings.dailyCefrLevels,
							);
							this.plugin.refreshView();
							this.refresh();
						}
					}),
			);

		new Setting(containerEl).setName("Daily CEFR levels").setHeading();

		const levelCounts = this.countWordsByLevel();
		const activeCount = this.plugin.deckStore.getActiveWords(
			this.plugin.settings.dailyWordCount,
			this.plugin.settings.dailyCefrLevels,
		).length;

		containerEl.createEl("p", {
			cls: "setting-item-description",
			text: `${activeCount} words selected. Toggle A1–C2 individually; at least one level must stay enabled.`,
		});

		for (const level of CEFR_LEVELS) {
			new Setting(containerEl)
				.setName(level)
				.setDesc(`${levelCounts[level] ?? 0} words`)
				.addToggle((toggle) =>
					toggle
						.setValue(this.plugin.settings.dailyCefrLevels.includes(level))
						.onChange(async (enabled) => {
							await this.setCefrLevel(level, enabled);
							toggle.setValue(this.plugin.settings.dailyCefrLevels.includes(level));
						}),
				);
		}

		new Setting(containerEl).setName("Pronunciation audio").setHeading();

		new Setting(containerEl)
			.setName("Download audio")
			.setDesc(
				this.plugin.settings.audioDownloaded
					? "Audio is available locally. You can re-run the download to fetch any missing files."
					: "Audio has not been downloaded yet. Download it from GitHub to enable playback.",
			)
			.addButton((button) =>
				button
					.setButtonText(
						this.plugin.settings.audioDownloaded ? "Re-download" : "Download",
					)
					.setCta()
					.onClick(() => {
						this.plugin.openAudioDownloadModal();
					}),
			);
	}

	private countWordsByLevel(): Record<CefrLevel, number> {
		const counts = Object.fromEntries(CEFR_LEVELS.map((level) => [level, 0])) as Record<
			CefrLevel,
			number
		>;

		try {
			for (const word of this.plugin.deckStore.getDeck().words) {
				if (word.cefr in counts) counts[word.cefr as CefrLevel] += 1;
			}
		} catch {
			// deck not loaded yet
		}

		return counts;
	}

	private async setCefrLevel(level: CefrLevel, enabled: boolean): Promise<void> {
		const selected = new Set(this.plugin.settings.dailyCefrLevels);

		if (enabled) {
			selected.add(level);
		} else {
			if (selected.size <= 1) {
				new Notice("Keep at least one CEFR level enabled");
				return;
			}
			selected.delete(level);
		}

		this.plugin.settings.dailyCefrLevels = CEFR_LEVELS.filter((item) => selected.has(item));
		await this.plugin.saveSettings();
		this.plugin.deckStore.clampCurrentIndex(
			this.plugin.settings.dailyWordCount,
			this.plugin.settings.dailyCefrLevels,
		);
		this.plugin.refreshView();
		this.refresh();
	}
}
