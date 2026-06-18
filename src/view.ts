import { ItemView, WorkspaceLeaf } from "obsidian";
import { DagensOrdCardRenderer } from "./card-renderer";
import type DagensOrdPlugin from "./main";

export const VIEW_TYPE = "dagens-ord-view";

export class DagensOrdView extends ItemView {
	private renderer: DagensOrdCardRenderer;

	constructor(leaf: WorkspaceLeaf, plugin: DagensOrdPlugin) {
		super(leaf);
		this.renderer = new DagensOrdCardRenderer(plugin, () => this.render());
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
		this.renderer.destroy();
	}

	render(): void {
		this.renderer.render(this.contentEl);
	}
}
