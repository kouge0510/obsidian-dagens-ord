import { App, normalizePath } from "obsidian";
import type { DeckData, UserProgress, WordEntry } from "./types";

const PROGRESS_FILE = "dagens-ord/progress.json";

export class DeckStore {
	private deck: DeckData | null = null;
	private progress: UserProgress = {
		currentIndex: 0,
		starred: [],
		mastered: [],
		lastDailyDate: "",
	};

	constructor(private app: App) {}

	async loadDeck(deckJson: string): Promise<void> {
		this.deck = JSON.parse(deckJson) as DeckData;
		await this.loadProgress();
	}

	getDeck(): DeckData {
		if (!this.deck) throw new Error("Deck not loaded");
		return this.deck;
	}

	getActiveWords(dailyWordCount: number, dailyCefrLevels: readonly string[]): WordEntry[] {
		const deck = this.getDeck();
		const levels = new Set(dailyCefrLevels);
		if (levels.size === 0) return [];

		const filtered = deck.words.filter((word) => levels.has(word.cefr));
		return filtered.slice(0, Math.min(dailyWordCount, filtered.length));
	}

	getWordAt(
		index: number,
		dailyWordCount: number,
		dailyCefrLevels: readonly string[],
	): WordEntry | null {
		const words = this.getActiveWords(dailyWordCount, dailyCefrLevels);
		if (index < 0 || index >= words.length) return null;
		return words[index];
	}

	getDailyIndex(dailyWordCount: number, dailyCefrLevels: readonly string[]): number {
		const words = this.getActiveWords(dailyWordCount, dailyCefrLevels);
		if (words.length === 0) return 0;
		const today = this.todayString();
		const dayNumber = this.daysSinceEpoch(today);
		return dayNumber % words.length;
	}

	getCurrentIndex(dailyWordCount: number, dailyCefrLevels: readonly string[]): number {
		const words = this.getActiveWords(dailyWordCount, dailyCefrLevels);
		if (words.length === 0) return 0;

		this.clampIndexToCount(words.length);

		const today = this.todayString();
		if (this.progress.lastDailyDate !== today) {
			this.progress.currentIndex = this.getDailyIndex(dailyWordCount, dailyCefrLevels);
			this.progress.lastDailyDate = today;
			void this.saveProgress();
		}
		return this.progress.currentIndex;
	}

	setCurrentIndex(index: number): void {
		this.progress.currentIndex = index;
		void this.saveProgress();
	}

	goToToday(dailyWordCount: number, dailyCefrLevels: readonly string[]): number {
		const words = this.getActiveWords(dailyWordCount, dailyCefrLevels);
		if (words.length === 0) {
			this.progress.currentIndex = 0;
			void this.saveProgress();
			return 0;
		}

		const idx = this.getDailyIndex(dailyWordCount, dailyCefrLevels);
		this.progress.currentIndex = idx;
		this.progress.lastDailyDate = this.todayString();
		void this.saveProgress();
		return idx;
	}

	clampCurrentIndex(dailyWordCount: number, dailyCefrLevels: readonly string[]): void {
		const words = this.getActiveWords(dailyWordCount, dailyCefrLevels);
		this.clampIndexToCount(words.length);
	}

	private clampIndexToCount(wordCount: number): void {
		if (wordCount === 0) {
			this.progress.currentIndex = 0;
			void this.saveProgress();
			return;
		}
		if (this.progress.currentIndex >= wordCount) {
			this.progress.currentIndex = wordCount - 1;
			void this.saveProgress();
		}
	}

	isStarred(wordId: string): boolean {
		return this.progress.starred.includes(wordId);
	}

	isMastered(wordId: string): boolean {
		return this.progress.mastered.includes(wordId);
	}

	toggleStarred(wordId: string): boolean {
		const idx = this.progress.starred.indexOf(wordId);
		if (idx >= 0) {
			this.progress.starred.splice(idx, 1);
			void this.saveProgress();
			return false;
		}
		this.progress.starred.push(wordId);
		void this.saveProgress();
		return true;
	}

	toggleMastered(wordId: string): boolean {
		const idx = this.progress.mastered.indexOf(wordId);
		if (idx >= 0) {
			this.progress.mastered.splice(idx, 1);
			void this.saveProgress();
			return false;
		}
		this.progress.mastered.push(wordId);
		void this.saveProgress();
		return true;
	}

	getStats(dailyWordCount: number, dailyCefrLevels: readonly string[]) {
		const words = this.getActiveWords(dailyWordCount, dailyCefrLevels);
		const activeIds = new Set(words.map((w) => w.id));
		return {
			total: words.length,
			mastered: this.progress.mastered.filter((id) => activeIds.has(id)).length,
			starred: this.progress.starred.filter((id) => activeIds.has(id)).length,
		};
	}

	getProgress(): UserProgress {
		return { ...this.progress };
	}

	private todayString(): string {
		const d = new Date();
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
	}

	private daysSinceEpoch(dateStr: string): number {
		const [y, m, d] = dateStr.split("-").map(Number);
		const date = new Date(y, m - 1, d);
		return Math.floor(date.getTime() / 86400000);
	}

	private progressPath(): string {
		return normalizePath(
			`${this.app.vault.configDir}/${PROGRESS_FILE}`,
		);
	}

	private async loadProgress(): Promise<void> {
		const path = this.progressPath();
		if (!(await this.app.vault.adapter.exists(path))) return;
		try {
			const raw = await this.app.vault.adapter.read(path);
			const parsed = JSON.parse(raw) as Partial<UserProgress>;
			this.progress = { ...this.progress, ...parsed };
		} catch {
			// keep defaults
		}
	}

	async saveProgress(): Promise<void> {
		const path = this.progressPath();
		const dir = path.substring(0, path.lastIndexOf("/"));
		if (!(await this.app.vault.adapter.exists(dir))) {
			await this.app.vault.adapter.mkdir(dir);
		}
		await this.app.vault.adapter.write(
			path,
			JSON.stringify(this.progress, null, 2),
		);
	}
}
