import { ItemView, Notice, WorkspaceLeaf } from "obsidian";
import type DagensOrdPlugin from "./main";
import { formatPlaybackRate, nextPlaybackRate } from "./playback-speed";
import type { WordEntry } from "./types";

export const VIEW_TYPE = "dagens-ord-view";

export class DagensOrdView extends ItemView {
	private audio: HTMLAudioElement | null = null;
	private wheelScrollCleanup: (() => void) | null = null;

	constructor(leaf: WorkspaceLeaf, private plugin: DagensOrdPlugin) {
		super(leaf);
	}

	getViewType(): string {
		return VIEW_TYPE;
	}

	getDisplayText(): string {
		return "Dagens ord";
	}

	getIcon(): string {
		return "languages";
	}

	async onOpen(): Promise<void> {
		this.render();
	}

	async onClose(): Promise<void> {
		this.cancelDampedScroll();
		if (this.audio) {
			this.audio.pause();
			this.audio = null;
		}
	}

	render(): void {
		const container = this.contentEl;
		container.empty();
		container.addClass("dagens-ord-container");

		const store = this.plugin.deckStore;
		const settings = this.plugin.settings;
		const { dailyWordCount, dailyCefrLevels } = settings;
		const index = store.getCurrentIndex(dailyWordCount, dailyCefrLevels);
		const word = store.getWordAt(index, dailyWordCount, dailyCefrLevels);

		if (!word) {
			container.createEl("p", {
				text: dailyCefrLevels.length === 0
					? "You should select at least one CEFR level。"
					: "Under current settings, no words found。",
			});
			return;
		}

		const stats = store.getStats(dailyWordCount, dailyCefrLevels);
		const card = container.createDiv({ cls: "dagens-ord-card" });

		this.renderHeader(card, stats, index);

		const scrollBody = card.createDiv({ cls: "do-card-scroll" });
		this.renderWord(scrollBody, word);
		this.renderExample(scrollBody, word);
		this.renderTags(scrollBody, word, store);
		scrollBody.scrollTop = 0;
		this.attachCardWheelScroll(card, scrollBody);

		this.renderActions(card, word, index, stats.total);
	}

	private cancelDampedScroll(): void {
		this.wheelScrollCleanup?.();
		this.wheelScrollCleanup = null;
	}

	private attachCardWheelScroll(card: HTMLElement, scrollEl: HTMLElement): void {
		this.cancelDampedScroll();

		let velocity = 0;
		let lastFrame = 0;
		let rafId: number | null = null;

		const FRICTION = 0.22;
		// 每帧速度保留多少；越接近 1，滑得越远
		const WHEEL_GAIN = 0.46; // 滚一下给多少初始速度
		const MAX_VELOCITY = 72;
		const STOP_THRESHOLD = 0.12;

		const maxScroll = () =>
			Math.max(0, scrollEl.scrollHeight - scrollEl.clientHeight);

		const wheelDelta = (e: WheelEvent): number => {
			if (e.deltaMode === WheelEvent.DOM_DELTA_LINE) return e.deltaY * 20;
			if (e.deltaMode === WheelEvent.DOM_DELTA_PAGE) {
				return e.deltaY * scrollEl.clientHeight * 0.9;
			}
			return e.deltaY;
		};

		const tick = (time: number) => {
			const dt = lastFrame ? Math.min(2.8, (time - lastFrame) / 16.667) : 1;
			lastFrame = time;

			if (Math.abs(velocity) < STOP_THRESHOLD) {
				velocity = 0;
				rafId = null;
				lastFrame = 0;
				return;
			}

			velocity *= Math.pow(FRICTION, dt);

			const max = maxScroll();
			let next = scrollEl.scrollTop + velocity * dt;

			if (next < 0) {
				next = 0;
				velocity = 0;
			} else if (next > max) {
				next = max;
				velocity = 0;
			}

			scrollEl.scrollTop = next;
			rafId = requestAnimationFrame(tick);
		};

		const start = () => {
			if (rafId === null) {
				lastFrame = 0;
				rafId = requestAnimationFrame(tick);
			}
		};

		const onWheel = (e: WheelEvent) => {
			if (e.target instanceof Element && e.target.closest(".do-actions")) return;
			if (scrollEl.scrollHeight <= scrollEl.clientHeight) return;

			const delta = wheelDelta(e);
			const max = maxScroll();
			const atRest = Math.abs(velocity) < STOP_THRESHOLD;
			if (atRest && scrollEl.scrollTop <= 0 && delta < 0) return;
			if (atRest && scrollEl.scrollTop >= max && delta > 0) return;

			e.preventDefault();
			e.stopPropagation();

			velocity += delta * WHEEL_GAIN;
			velocity = Math.max(-MAX_VELOCITY, Math.min(MAX_VELOCITY, velocity));
			start();
		};

		card.addEventListener("wheel", onWheel, { passive: false, capture: true });

		this.wheelScrollCleanup = () => {
			card.removeEventListener("wheel", onWheel, { capture: true });
			if (rafId !== null) {
				cancelAnimationFrame(rafId);
				rafId = null;
			}
		};
	}

	private renderHeader(
		card: HTMLElement,
		stats: { total: number; mastered: number; starred: number },
		index: number,
	): void {
		const header = card.createDiv({ cls: "do-header" });
		const titleRow = header.createDiv({ cls: "do-title-row" });

		titleRow.createDiv({
			cls: "do-flag",
			attr: { "aria-hidden": "true" },
		});

		const titleBlock = titleRow.createDiv({ cls: "do-title-block" });
		titleBlock.createEl("h2", { text: "Dagens ord" });

		const meta = titleBlock.createDiv({ cls: "do-meta" });
		meta.setText(
			`${stats.total} words • #${index + 1} • ${stats.mastered}✓ • ${stats.starred}★`,
		);
	}

	private renderWord(card: HTMLElement, word: WordEntry): void {
		const section = card.createDiv({ cls: "do-word-section" });

		const wordRow = section.createDiv({ cls: "do-word-row" });
		const wordEl = wordRow.createEl("h1", { cls: "do-word", text: word.word });

		const playBtn = wordRow.createEl("button", {
			cls: "do-play-btn",
			attr: { "aria-label": "播放发音" },
		});
		playBtn.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
		playBtn.addEventListener("click", () =>
			void this.playAudio(`word-${word.id}`, word.audioWord),
		);

		this.renderSpeedButton(wordRow);

		if (word.ipa) {
			section.createEl("p", { cls: "do-ipa", text: word.ipa });
		}

		const translationsEn = word.translationsEn.filter(Boolean);
		const transTextEn = translationsEn.slice(0, 2).join(" • ");
		if (transTextEn) {
			section.createEl("p", { cls: "do-translation do-translation-en", text: transTextEn });
		}

		const translationsZh = (word.translationsZh ?? []).filter(Boolean);
		const transTextZh = translationsZh.slice(0, 2).join(" • ");
		if (transTextZh) {
			section.createEl("p", { cls: "do-translation do-translation-zh", text: transTextZh });
		}
	}

	private renderExample(card: HTMLElement, word: WordEntry): void {
		if (!word.exampleDa) return;

		const box = card.createDiv({ cls: "do-example-box" });
		box.createEl("p", { cls: "do-example-da", text: word.exampleDa });

		const exampleEn = (word.exampleEn ?? "").trim();
		const exampleZh = (word.exampleZh ?? "").trim();
		if (exampleEn || exampleZh) {
			const translations = box.createDiv({ cls: "do-example-translations" });
			if (exampleEn) {
				translations.createEl("p", { cls: "do-example-en", text: exampleEn });
			}
			if (exampleZh) {
				translations.createEl("p", { cls: "do-example-zh", text: exampleZh });
			}
		}

		const playEx = box.createEl("button", {
			cls: "do-play-inline",
			attr: { "aria-label": "播放例句" },
		});
		playEx.innerHTML = `<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
		playEx.addEventListener("click", () =>
			void this.playAudio(`ex-${word.id}`, null),
		);
	}

	private renderSpeedButton(parent: HTMLElement): void {
		const button = parent.createEl("button", {
			cls: "do-speed-btn",
			text: formatPlaybackRate(this.plugin.settings.playbackRate),
			attr: { "aria-label": "切换播放速度" },
		});
		button.addEventListener("click", async () => {
			const nextRate = nextPlaybackRate(this.plugin.settings.playbackRate);
			this.plugin.settings.playbackRate = nextRate;
			if (this.audio) this.audio.playbackRate = nextRate;
			button.setText(formatPlaybackRate(nextRate));
			await this.plugin.saveSettings();
		});
	}

	private renderTags(
		card: HTMLElement,
		word: WordEntry,
		store: DagensOrdPlugin["deckStore"],
	): void {
		const tags = card.createDiv({ cls: "do-tags" });
		const status = store.isMastered(word.id) ? "mastered" : "unmastered";

		for (const label of [word.cefr, "daily", word.pos, status]) {
			tags.createEl("span", { cls: "do-tag", text: label });
		}
	}

	private renderActions(
		card: HTMLElement,
		word: WordEntry,
		index: number,
		total: number,
	): void {
		const actions = card.createDiv({ cls: "do-actions" });
		const store = this.plugin.deckStore;
		const { dailyWordCount, dailyCefrLevels } = this.plugin.settings;

		const nav = actions.createDiv({ cls: "do-nav" });

		const prevBtn = nav.createEl("button", { cls: "do-btn do-btn-icon", text: "←" });
		prevBtn.addEventListener("click", () => {
			const newIdx = (index - 1 + total) % total;
			store.setCurrentIndex(newIdx);
			this.render();
		});

		const nextBtn = nav.createEl("button", { cls: "do-btn do-btn-icon", text: "→" });
		nextBtn.addEventListener("click", () => {
			const newIdx = (index + 1) % total;
			store.setCurrentIndex(newIdx);
			this.render();
		});

		const starBtn = actions.createEl("button", {
			cls: `do-btn do-btn-action${store.isStarred(word.id) ? " active" : ""}`,
		});
		starBtn.innerHTML = `${store.isStarred(word.id) ? "★" : "☆"} Star`;
		starBtn.addEventListener("click", () => {
			store.toggleStarred(word.id);
			this.render();
		});

		const masterBtn = actions.createEl("button", {
			cls: `do-btn do-btn-action${store.isMastered(word.id) ? " active" : ""}`,
		});
		masterBtn.innerHTML = `${store.isMastered(word.id) ? "✓" : "○"} Mastered`;
		masterBtn.addEventListener("click", () => {
			store.toggleMastered(word.id);
			this.render();
		});

		const todayBtn = actions.createEl("button", {
			cls: "do-btn do-btn-action",
			text: "Today",
		});
		todayBtn.addEventListener("click", () => {
			store.goToToday(dailyWordCount, dailyCefrLevels);
			this.render();
		});
	}

	private async playAudio(cacheKey: string, ankiFile?: string | null): Promise<void> {
		try {
			const { buffer, mime } = await this.plugin.audio.getAudio(cacheKey, ankiFile);
			const blob = new Blob([buffer], { type: mime });
			const url = URL.createObjectURL(blob);

			if (this.audio) {
				this.audio.pause();
				URL.revokeObjectURL(this.audio.src);
			}

			this.audio = new Audio(url);
			this.audio.playbackRate = this.plugin.settings.playbackRate;
			this.audio.onended = () => URL.revokeObjectURL(url);
			await this.audio.play();
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			new Notice(`语音播放失败: ${msg}`);
		}
	}
}
