<script lang="ts">
	import type { UnknownBook } from '$lib/types';

	interface ReviewEntry {
		original_title: string;
		corrected_title: string;
		photo_index: number;
	}

	interface Props {
		books: UnknownBook[];
		submitting?: boolean;
		onsubmit: (entries: ReviewEntry[]) => void;
	}

	let { books, submitting = false, onsubmit }: Props = $props();

	let entries = $state<ReviewEntry[]>([]);

	$effect(() => {
		entries = books.map((book) => ({
			original_title: book.title,
			corrected_title: book.title,
			photo_index: book.photo_index
		}));
	});

	function handleSubmit() {
		const valid = entries.filter((entry) => entry.corrected_title.trim().length > 0);
		if (valid.length > 0) {
			onsubmit(valid);
		}
	}
</script>

<div class="rounded-2xl border border-amber-200 bg-amber-50 p-5">
	<h2 class="text-sm font-semibold text-amber-900">Manual review</h2>
	<p class="mt-1 text-xs text-amber-800">
		These titles could not be matched automatically. Correct them and retry.
	</p>

	<div class="mt-4 space-y-3">
		{#each entries as entry, index (entry.photo_index + '-' + index)}
			<div class="rounded-xl bg-white p-3 shadow-sm">
				<label class="block text-xs text-stone-500" for="title-{index}">
					Photo {entry.photo_index + 1}
					{#if entry.original_title}
						· detected as “{entry.original_title}”
					{:else}
						· no title detected
					{/if}
				</label>
				<input
					id="title-{index}"
					type="text"
					class="mt-1 w-full rounded-lg border border-stone-200 px-3 py-2 text-sm text-stone-900 outline-none focus:border-stone-400"
					placeholder="Enter book title"
					bind:value={entry.corrected_title}
					disabled={submitting}
				/>
			</div>
		{/each}
	</div>

	<button
		type="button"
		class="mt-4 w-full rounded-xl bg-amber-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-amber-800 disabled:opacity-50"
		disabled={submitting}
		onclick={handleSubmit}
	>
		{submitting ? 'Submitting…' : 'Add corrected titles'}
	</button>
</div>
