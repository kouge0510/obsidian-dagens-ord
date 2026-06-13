export const PLAYBACK_RATES = [0.75, 1, 1.25, 1.5, 2] as const;

export function normalizePlaybackRate(rate: number): number {
	return PLAYBACK_RATES.includes(rate as (typeof PLAYBACK_RATES)[number])
		? rate
		: 1;
}

export function nextPlaybackRate(currentRate: number): number {
	const normalized = normalizePlaybackRate(currentRate);
	const currentIndex = PLAYBACK_RATES.indexOf(
		normalized as (typeof PLAYBACK_RATES)[number],
	);
	return PLAYBACK_RATES[(currentIndex + 1) % PLAYBACK_RATES.length];
}

export function formatPlaybackRate(rate: number): string {
	const normalized = normalizePlaybackRate(rate);
	return Number.isInteger(normalized) ? `${normalized}.0x` : `${normalized}x`;
}
