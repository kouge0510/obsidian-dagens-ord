export interface WordEntry { // 词条数据
	id: string;
	word: string;
	rank: number;
	pos: string;
	ipa: string | null;
	translationEn: string;
	translationsEn: string[];
	translationZh?: string;
	translationsZh?: string[];
	exampleDa: string;
	exampleZh?: string;
	exampleEn?: string;
	examplesZh?: string[];
	examplesEn?: string[];
	examplesDa: string[];
	cefr: string;
	index: number;
	audioWord?: string | null;
}

export interface DeckData {
	total: number;
	words: WordEntry[];
}

export interface UserProgress {
	currentIndex: number;
	starred: string[];
	mastered: string[];
	lastDailyDate: string;
}

export interface DagensOrdSettings {
	dailyWordCount: number;
	playbackRate: number;
	dailyCefrLevels: CefrLevel[];
}

export const CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"] as const;
export type CefrLevel = (typeof CEFR_LEVELS)[number];

export const DEFAULT_SETTINGS: DagensOrdSettings = {
	dailyWordCount: 4442,
	playbackRate: 1,
	dailyCefrLevels: [...CEFR_LEVELS],
};
