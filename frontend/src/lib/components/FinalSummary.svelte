<script lang="ts">
	import type { JobProgress } from '$lib/types';

	interface Props {
		progress: JobProgress;
		onreset: () => void;
	}

	let { progress, onreset }: Props = $props();

	const statusColors: Record<string, string> = {
		on_shelf: 'text-stone-600',
		added: 'text-emerald-700',
		unknown: 'text-amber-700',
		failed: 'text-red-700'
	};

	const statusLabels: Record<string, string> = {
		on_shelf: 'Already on shelf',
		added: 'Added',
		unknown: 'Needs review',
		failed: 'Failed'
	};
</script>

<div class="space-y-5">
	<div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
		<h2 class="text-lg font-semibold text-stone-900">Summary</h2>
		<p class="mt-1 text-sm text-stone-600">
			Processed {progress.total_photos} photo{progress.total_photos === 1 ? '' : 's'}.
		</p>

		<dl class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
			<div class="rounded-xl bg-stone-50 p-3 text-center">
				<dt class="text-xs text-stone-500">Detected</dt>
				<dd class="text-2xl font-semibold">{progress.books_found}</dd>
			</div>
			<div class="rounded-xl bg-stone-50 p-3 text-center">
				<dt class="text-xs text-stone-500">On shelf</dt>
				<dd class="text-2xl font-semibold">{progress.books_on_shelf}</dd>
			</div>
			<div class="rounded-xl bg-stone-50 p-3 text-center">
				<dt class="text-xs text-stone-500">Added</dt>
				<dd class="text-2xl font-semibold text-emerald-700">{progress.books_added}</dd>
			</div>
			<div class="rounded-xl bg-stone-50 p-3 text-center">
				<dt class="text-xs text-stone-500">Needs review</dt>
				<dd class="text-2xl font-semibold text-amber-700">{progress.unknown_books.length}</dd>
			</div>
		</dl>
	</div>

	{#if progress.results.length > 0}
		<div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
			<h3 class="text-sm font-medium text-stone-800">Books</h3>
			<ul class="mt-3 divide-y divide-stone-100">
				{#each progress.results as result (result.title + result.photo_index)}
					<li class="flex items-center justify-between py-2 text-sm">
						<span class="truncate pr-4 text-stone-800">{result.title}</span>
						<span class={`shrink-0 text-xs font-medium ${statusColors[result.status]}`}>
							{statusLabels[result.status]}
						</span>
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	{#if progress.error}
		<p class="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{progress.error}</p>
	{/if}

	<button
		type="button"
		class="w-full rounded-xl border border-stone-300 bg-white px-6 py-3 text-sm font-medium text-stone-800 transition hover:bg-stone-50"
		onclick={onreset}
	>
		Sync more photos
	</button>
</div>
