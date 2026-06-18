import { DagensOrdCardRenderer } from "./card-renderer";
import type DagensOrdPlugin from "./main";
import type { FloatingCardPosition } from "./types";

const DEFAULT_MARGIN = 24;
const DEFAULT_BOTTOM_OFFSET = 96;
const MINI_BUTTON_SIZE = 52;

export class FloatingCardController {
	private rootEl: HTMLElement | null = null;
	private openButtonEl: HTMLButtonElement | null = null;
	private renderer: DagensOrdCardRenderer;
	private resizeHandler = () => this.clampToViewport();

	constructor(private plugin: DagensOrdPlugin) {
		this.renderer = new DagensOrdCardRenderer(plugin, () => this.render());
	}

	sync(): void {
		if (this.plugin.settings.cardDisplayMode !== "floating") {
			this.destroy();
			return;
		}

		if (this.plugin.settings.floatingCardHidden) {
			this.showOpenButton();
		} else {
			this.render();
		}
	}

	render(): void {
		this.removeOpenButton();

		const root = this.ensureRoot();
		root.removeClass("is-hidden");
		this.applyStoredPosition(root);

		this.renderer.render(root, (card) => this.renderFloatingControls(card));
		window.requestAnimationFrame(() => this.clampToViewport());
	}

	destroy(): void {
		this.renderer.destroy();
		this.removeRoot();
		this.removeOpenButton();
		window.removeEventListener("resize", this.resizeHandler);
	}

	private ensureRoot(): HTMLElement {
		if (this.rootEl) return this.rootEl;

		this.rootEl = document.body.createDiv({ cls: "dagens-ord-floating-root" });
		window.addEventListener("resize", this.resizeHandler);
		return this.rootEl;
	}

	private removeRoot(): void {
		this.rootEl?.remove();
		this.rootEl = null;
	}

	private showOpenButton(): void {
		this.renderer.destroy();
		this.removeRoot();

		if (!this.openButtonEl) {
			this.openButtonEl = document.body.createEl("button", {
				cls: "dagens-ord-floating-open",
				text: "Open",
				attr: { "aria-label": "Open Dagens ord card" },
			});
			this.openButtonEl.addEventListener("click", () => {
				this.plugin.settings.floatingCardHidden = false;
				void this.plugin.saveSettings();
				this.render();
			});
		}

		this.applyStoredPosition(this.openButtonEl, MINI_BUTTON_SIZE, MINI_BUTTON_SIZE);
		window.addEventListener("resize", this.resizeHandler);
	}

	private removeOpenButton(): void {
		this.openButtonEl?.remove();
		this.openButtonEl = null;
	}

	private renderFloatingControls(card: HTMLElement): void {
		card.addClass("dagens-ord-card-floating");

		const controls = card.createDiv({ cls: "do-floating-controls" });
		const dragHandle = controls.createEl("button", {
			cls: "do-floating-drag",
			text: "Drag",
			attr: { "aria-label": "Drag Dagens ord card" },
		});
		const hideButton = controls.createEl("button", {
			cls: "do-floating-hide",
			text: "Hide",
			attr: { "aria-label": "Hide Dagens ord card" },
		});

		this.attachDrag(dragHandle);
		hideButton.addEventListener("click", () => {
			this.plugin.settings.floatingCardHidden = true;
			void this.plugin.saveSettings();
			this.showOpenButton();
		});
	}

	private attachDrag(handle: HTMLElement): void {
		let startPointerX = 0;
		let startPointerY = 0;
		let startLeft = 0;
		let startTop = 0;

		const onPointerMove = (event: PointerEvent) => {
			const root = this.rootEl;
			if (!root) return;

			const nextLeft = startLeft + event.clientX - startPointerX;
			const nextTop = startTop + event.clientY - startPointerY;
			this.applyPosition(root, this.clampPosition(root, { left: nextLeft, top: nextTop }));
		};

		const onPointerUp = () => {
			document.removeEventListener("pointermove", onPointerMove);
			document.removeEventListener("pointerup", onPointerUp);

			const root = this.rootEl;
			if (!root) return;
			const rect = root.getBoundingClientRect();
			this.plugin.settings.floatingCardPosition = {
				left: Math.round(rect.left),
				top: Math.round(rect.top),
			};
			void this.plugin.saveSettings();
		};

		handle.addEventListener("pointerdown", (event) => {
			const root = this.rootEl;
			if (!root) return;

			event.preventDefault();
			const rect = root.getBoundingClientRect();
			startPointerX = event.clientX;
			startPointerY = event.clientY;
			startLeft = rect.left;
			startTop = rect.top;

			document.addEventListener("pointermove", onPointerMove);
			document.addEventListener("pointerup", onPointerUp);
		});
	}

	private applyStoredPosition(el: HTMLElement, width?: number, height?: number): void {
		const position = this.getStoredOrDefaultPosition(el, width, height);
		this.applyPosition(el, this.clampPosition(el, position, width, height));
	}

	private getStoredOrDefaultPosition(
		el: HTMLElement,
		width?: number,
		height?: number,
	): FloatingCardPosition {
		const position = this.plugin.settings.floatingCardPosition;
		if (position.left > 0 || position.top > 0) return position;

		const rect = el.getBoundingClientRect();
		const elWidth = width ?? rect.width;
		const elHeight = height ?? rect.height;

		return {
			left: window.innerWidth - elWidth - DEFAULT_MARGIN,
			top: window.innerHeight - elHeight - DEFAULT_BOTTOM_OFFSET,
		};
	}

	private clampToViewport(): void {
		const el = this.rootEl ?? this.openButtonEl;
		if (!el) return;

		const position = this.clampPosition(el, this.getStoredOrDefaultPosition(el));
		this.applyPosition(el, position);
	}

	private clampPosition(
		el: HTMLElement,
		position: FloatingCardPosition,
		width?: number,
		height?: number,
	): FloatingCardPosition {
		const rect = el.getBoundingClientRect();
		const elWidth = width ?? rect.width;
		const elHeight = height ?? rect.height;
		const maxLeft = Math.max(DEFAULT_MARGIN, window.innerWidth - elWidth - DEFAULT_MARGIN);
		const maxTop = Math.max(DEFAULT_MARGIN, window.innerHeight - elHeight - DEFAULT_MARGIN);

		return {
			left: Math.max(DEFAULT_MARGIN, Math.min(maxLeft, position.left)),
			top: Math.max(DEFAULT_MARGIN, Math.min(maxTop, position.top)),
		};
	}

	private applyPosition(el: HTMLElement, position: FloatingCardPosition): void {
		el.style.left = `${position.left}px`;
		el.style.top = `${position.top}px`;
	}
}
