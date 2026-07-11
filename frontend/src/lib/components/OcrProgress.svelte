<script lang="ts">
	import ProgressBar from '$lib/components/ProgressBar.svelte';
	import type { PhotoOcrResult, ScanProgress } from '$lib/ocr/extract';

	interface Props {
		progress: ScanProgress | null;
		completed: PhotoOcrResult[];
	}

	let { progress, completed }: Props = $props();

	let percent = $derived(
		progress && progress.total > 0
			? Math.round(((progress.photo_index + progress.percent / 100) / progress.total) * 100)
			: 0
	);
</script>

{#if progress}
	<div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
		<div class="mb-1 flex items-center justify-between text-sm">
			<span class="font-medium text-stone-800">Reading covers on your phone</span>
			<span class="tabular-nums text-stone-500">{percent}%</span>
		</div>

		<div class="mb-3 flex items-center justify-between text-xs text-stone-500">
			<span>Photo {progress.photo_index + 1} of {progress.total}</span>
			<span>Step 2 of 4</span>
		</div>

		<ProgressBar value={percent} />

		<p class="mt-4 text-sm text-stone-600">{progress.message}</p>
		<p class="mt-1 text-xs text-stone-500">Photos never leave your device — only titles are sent.</p>

		{#if completed.length > 0}
			<ul class="mt-4 space-y-2 border-t border-stone-100 pt-4">
				{#each completed as result (result.photo_index)}
					<li class="flex items-start justify-between gap-3 text-sm">
						<span class="shrink-0 text-xs font-medium text-stone-400">#{result.photo_index + 1}</span>
						{#if result.titles.length > 0}
							<span class="min-w-0 flex-1 truncate text-right text-stone-800">
								“{result.titles[0]}”
							</span>
							<span class="shrink-0 text-xs text-emerald-700">found</span>
						{:else}
							<span class="min-w-0 flex-1 text-right text-stone-500 italic">No title detected</span>
							<span class="shrink-0 text-xs text-amber-700">review</span>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</div>
{/if}
