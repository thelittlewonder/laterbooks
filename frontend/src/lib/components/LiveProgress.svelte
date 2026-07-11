<script lang="ts">
	import ProgressBar from '$lib/components/ProgressBar.svelte';
	import type { JobProgress, ProcessingStep } from '$lib/types';

	interface Props {
		progress: JobProgress | null;
	}

	let { progress }: Props = $props();

	const stepLabel: Record<ProcessingStep, string> = {
		idle: 'Starting',
		ocr: 'Reading cover',
		checking: 'Checking shelf',
		adding: 'Syncing to Goodreads',
		cleanup: 'Cleaning up'
	};

	const stepWeight: Record<ProcessingStep, number> = {
		idle: 0,
		ocr: 0.2,
		cleanup: 0.35,
		checking: 0.55,
		adding: 0.75
	};

	const statusLabels: Record<string, string> = {
		on_shelf: 'On shelf',
		added: 'Added',
		unknown: 'Needs review',
		failed: 'Failed'
	};

	const statusColors: Record<string, string> = {
		on_shelf: 'text-stone-500',
		added: 'text-emerald-700',
		unknown: 'text-amber-700',
		failed: 'text-red-700'
	};

	let percent = $derived.by(() => {
		if (!progress || progress.total_photos <= 0) {
			return progress?.status === 'pending' ? 5 : 0;
		}

		const completed = progress.photos_completed ?? 0;
		const inPhoto = progress.status === 'processing' ? (stepWeight[progress.current_step] ?? 0) : 0;
		const raw = ((completed + inPhoto) / progress.total_photos) * 100;
		return Math.min(100, Math.round(raw));
	});

	let recentResults = $derived(progress?.results.slice(-4).reverse() ?? []);

	let titlePrefix = $derived(
		progress?.current_step === 'adding' ? 'Now syncing:' : 'Now checking:'
	);
</script>

{#if progress}
	<div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
		<div class="mb-1 flex items-center justify-between text-sm">
			<span class="font-medium text-stone-800">
				{stepLabel[progress.current_step] ?? 'Syncing Goodreads'}
			</span>
			<span class="tabular-nums text-stone-500">{percent}%</span>
		</div>

		<div class="mb-3 flex items-center justify-between text-xs text-stone-500">
			<span>
				{#if progress.status === 'processing' && progress.current_photo > 0}
					Working on photo {progress.current_photo} of {progress.total_photos}
				{:else}
					{progress.photos_completed ?? 0} of {progress.total_photos} photos done
				{/if}
			</span>
			<span>{progress.photos_completed ?? 0} of {progress.total_photos} complete</span>
		</div>

		<ProgressBar value={percent} />

		{#if progress.current_title}
			<p class="mt-4 truncate text-sm text-stone-800">
				<span class="text-stone-500">{titlePrefix}</span> “{progress.current_title}”
			</p>
		{:else if progress.message}
			<p class="mt-4 text-sm text-stone-600">{progress.message}</p>
		{/if}

		<dl class="mt-4 grid grid-cols-3 gap-3 text-center text-xs">
			<div class="rounded-lg bg-stone-50 px-2 py-2">
				<dt class="text-stone-500">Detected</dt>
				<dd class="text-lg font-semibold text-stone-900">{progress.books_found}</dd>
			</div>
			<div class="rounded-lg bg-stone-50 px-2 py-2">
				<dt class="text-stone-500">On shelf</dt>
				<dd class="text-lg font-semibold text-stone-900">{progress.books_on_shelf}</dd>
			</div>
			<div class="rounded-lg bg-stone-50 px-2 py-2">
				<dt class="text-stone-500">Added</dt>
				<dd class="text-lg font-semibold text-emerald-700">{progress.books_added}</dd>
			</div>
		</dl>

		{#if recentResults.length > 0}
			<div class="mt-4 border-t border-stone-100 pt-4">
				<p class="mb-2 text-xs font-medium uppercase tracking-wide text-stone-400">Recent</p>
				<ul class="space-y-2">
					{#each recentResults as result (result.title + result.photo_index + result.status)}
						<li class="flex items-center justify-between gap-3 text-sm">
							<span class="min-w-0 truncate text-stone-800">{result.title}</span>
							<span class={`shrink-0 text-xs font-medium ${statusColors[result.status]}`}>
								{statusLabels[result.status]}
							</span>
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	</div>
{/if}
