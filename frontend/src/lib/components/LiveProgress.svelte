<script lang="ts">
	import type { JobProgress } from '$lib/types';

	interface Props {
		progress: JobProgress | null;
	}

	let { progress }: Props = $props();

	const stepLabel: Record<string, string> = {
		idle: 'Starting',
		ocr: 'Reading cover',
		checking: 'Checking shelf',
		adding: 'Adding book',
		cleanup: 'Cleaning up'
	};

	let percent = $derived(
		progress && progress.total_photos > 0
			? Math.round((progress.current_photo / progress.total_photos) * 100)
			: 0
	);
</script>

{#if progress}
	<div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
		<div class="mb-3 flex items-center justify-between text-sm">
			<span class="font-medium text-stone-800">
				{stepLabel[progress.current_step] ?? 'Processing'}
			</span>
			<span class="text-stone-500">
				Photo {progress.current_photo} / {progress.total_photos}
			</span>
		</div>

		<div class="mb-4 h-2 overflow-hidden rounded-full bg-stone-100">
			<div
				class="h-full rounded-full bg-stone-800 transition-all duration-500"
				style="width: {percent}%"
			></div>
		</div>

		{#if progress.current_title}
			<p class="truncate text-sm text-stone-600">“{progress.current_title}”</p>
		{:else if progress.message}
			<p class="text-sm text-stone-600">{progress.message}</p>
		{/if}

		<dl class="mt-4 grid grid-cols-3 gap-3 text-center text-xs">
			<div class="rounded-lg bg-stone-50 px-2 py-2">
				<dt class="text-stone-500">Found</dt>
				<dd class="text-lg font-semibold text-stone-900">{progress.books_found}</dd>
			</div>
			<div class="rounded-lg bg-stone-50 px-2 py-2">
				<dt class="text-stone-500">On shelf</dt>
				<dd class="text-lg font-semibold text-stone-900">{progress.books_on_shelf}</dd>
			</div>
			<div class="rounded-lg bg-stone-50 px-2 py-2">
				<dt class="text-stone-500">Added</dt>
				<dd class="text-lg font-semibold text-stone-900">{progress.books_added}</dd>
			</div>
		</dl>
	</div>
{/if}
