<script lang="ts">
	const MAX_PHOTOS = 10;

	interface Props {
		files: File[];
		disabled?: boolean;
		onchange: (files: File[]) => void;
	}

	let { files, disabled = false, onchange }: Props = $props();

	let previews = $derived(
		files.map((file) => ({
			file,
			url: URL.createObjectURL(file)
		}))
	);

	function handleSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		if (!input.files) return;

		const selected = Array.from(input.files).slice(0, MAX_PHOTOS);
		onchange(selected);
		input.value = '';
	}

	function removeAt(index: number) {
		onchange(files.filter((_, i) => i !== index));
	}

	$effect(() => {
		return () => {
			for (const preview of previews) {
				URL.revokeObjectURL(preview.url);
			}
		};
	});
</script>

<div class="space-y-4">
	<label
		class="flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-stone-300 bg-white px-6 py-10 transition hover:border-stone-400 hover:bg-stone-50 {disabled
			? 'pointer-events-none opacity-50'
			: ''}"
	>
		<span class="text-sm font-medium text-stone-700">Select up to {MAX_PHOTOS} cover photos</span>
		<span class="mt-1 text-xs text-stone-500">One book per photo — make it the biggest thing in frame</span>
		<input
			type="file"
			accept="image/*"
			multiple
			class="sr-only"
			{disabled}
			onchange={handleSelect}
		/>
	</label>

	{#if previews.length > 0}
		<div class="grid grid-cols-3 gap-3 sm:grid-cols-5">
			{#each previews as preview, index (preview.url)}
				<div class="group relative aspect-[3/4] overflow-hidden rounded-xl bg-stone-100">
					<img src={preview.url} alt="Book cover {index + 1}" class="h-full w-full object-cover" />
					{#if !disabled}
						<button
							type="button"
							class="absolute right-1 top-1 min-h-7 min-w-7 rounded-full bg-black/60 text-sm text-white"
							onclick={() => removeAt(index)}
							aria-label="Remove photo {index + 1}"
						>
							×
						</button>
					{/if}
				</div>
			{/each}
		</div>
		<p class="text-center text-xs text-stone-500">{files.length} of {MAX_PHOTOS} selected</p>
	{/if}
</div>
