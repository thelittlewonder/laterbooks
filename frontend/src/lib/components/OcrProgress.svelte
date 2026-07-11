<script lang="ts">
	import type { ScanProgress } from '$lib/ocr/extract';

	interface Props {
		progress: ScanProgress | null;
	}

	let { progress }: Props = $props();

	let percent = $derived(
		progress && progress.total > 0
			? Math.round(((progress.photo_index + progress.percent / 100) / progress.total) * 100)
			: 0
	);
</script>

{#if progress}
	<div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
		<div class="mb-3 flex items-center justify-between text-sm">
			<span class="font-medium text-stone-800">Reading covers on your phone</span>
			<span class="text-stone-500">
				Photo {progress.photo_index + 1} / {progress.total}
			</span>
		</div>

		<div class="mb-4 h-2 overflow-hidden rounded-full bg-stone-100">
			<div
				class="h-full rounded-full bg-stone-800 transition-all duration-300"
				style="width: {percent}%"
			></div>
		</div>

		<p class="text-sm text-stone-600">{progress.message}</p>
		<p class="mt-2 text-xs text-stone-500">Photos never leave your device — only titles are sent.</p>
	</div>
{/if}
